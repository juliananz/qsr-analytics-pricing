"""
Build fact_sales_margin.parquet
================================
Calcula margenes de venta con costos unitarios.

Schema del output (CONTRATO - NO CAMBIAR):
- sale_date: datetime64[ns]
- product_name: str
- product_code: str (nullable)
- bundle_code: str (nullable)
- quantity: float
- net_amount: float
- unit_cost: float (NUNCA NaN)
- total_cost: float
- gross_margin: float
- gross_margin_pct: float
- cost_estimated: bool
- non_product_revenue: bool
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings
from typing import Dict, Tuple


# ============================================================
# CONFIGURACION DE RUTAS
# ============================================================

SALES_FILE = Path("data/analytics/fact_sales_raw.parquet")
PRODUCT_COST_FILE = Path("data/processed_data/product_unit_cost.csv")
BUNDLE_COST_FILE = Path("data/processed_data/bundle_unit_cost.csv")
MAPPING_FILE = Path("data/processed_data/product_name_mapping.csv")
EXPECTED_DRINK_COST_FILE = Path("data/processed_data/expected_drink_cost.csv")

OUTPUT_FILE = Path("data/analytics/fact_sales_margin.parquet")


# ============================================================
# CONFIGURACION DE REGLAS DE NEGOCIO
# ============================================================

# Keywords para clasificacion
NON_PRODUCT_KEYWORDS = ["ENVIO", "EXCESO", "AJUSTE", "EFECTIVO", "$"]
DRINK_KEYWORDS = ["REFRESCO", "COCA", "FANTA", "SPRITE", "FUZE", "AGUA"]

# Costos fijos especificos
AVOCADO_COST = 5.0
FALLBACK_DRINK_COST = 8.0

# Margen objetivo para estimacion de costos
TARGET_MARGIN_PCT = 0.45  # 45% margen -> costo = precio * (1 - 0.45) = precio * 0.55
COST_ESTIMATION_MULTIPLIER = 1 - TARGET_MARGIN_PCT  # 0.55


# ============================================================
# SCHEMA DE OUTPUT
# ============================================================

OUTPUT_SCHEMA = {
    "sale_date": "datetime64[ns]",
    "product_name": "str",
    "product_code": "str",
    "bundle_code": "str",
    "quantity": "float64",
    "net_amount": "float64",
    "unit_cost": "float64",
    "total_cost": "float64",
    "gross_margin": "float64",
    "gross_margin_pct": "float64",
    "cost_estimated": "bool",
    "non_product_revenue": "bool",
}


# ============================================================
# UTILIDADES
# ============================================================

def normalize_text(s: str) -> str:
    """Normaliza nombres de productos para matching"""
    if pd.isna(s):
        return ""
    return str(s).upper().strip().replace("\n", " ")


def load_cost_map(file: Path, key_col: str, value_col: str = "unit_cost") -> Dict:
    """Carga un CSV de costos en un diccionario"""
    if not file.exists():
        warnings.warn(f"Cost file not found: {file}")
        return {}
    df = pd.read_csv(file)
    return df.set_index(key_col)[value_col].to_dict()


def load_expected_drink_cost() -> float:
    """Carga el costo esperado de bebidas desde CSV o usa fallback"""
    if EXPECTED_DRINK_COST_FILE.exists():
        drink_df = pd.read_csv(EXPECTED_DRINK_COST_FILE)
        cost = float(drink_df["expected_unit_cost"].iloc[0])
        return cost
    else:
        warnings.warn(f"Using fallback drink cost: ${FALLBACK_DRINK_COST}")
        return FALLBACK_DRINK_COST


# ============================================================
# RESOLUCION DE COSTOS
# ============================================================

def resolve_unit_cost(
    row: pd.Series,
    product_costs: Dict,
    bundle_costs: Dict,
    expected_drink_cost: float
) -> Tuple[float, bool]:
    """
    Resuelve el costo unitario de un item.
    SIEMPRE retorna un valor (nunca NaN).
    
    Orden de precedencia:
    1. Ingresos no operativos -> costo = precio (margen 0)
    2. Paquetes -> costo del bundle
    3. Bebidas -> costo esperado
    4. Extra aguacate -> costo fijo
    5. Producto mapeado -> costo del catalogo
    6. Fallback -> costo estimado basado en margen objetivo
    
    Args:
        row: Fila del DataFrame
        product_costs: Dict de costos por product_code
        bundle_costs: Dict de costos por bundle_code
        expected_drink_cost: Costo esperado de bebidas
    
    Returns:
        Tuple[float, bool]: (unit_cost, is_estimated)
    """
    name = row["product_name_norm"]
    
    # 1. Ingresos no operativos: costo = precio (margen 0)
    if row["non_product_revenue"]:
        if row["cantidad"] > 0:
            return row["importe"] / row["cantidad"], False
        return row["importe"], False
    
    # 2. Paquetes: buscar en bundle_costs
    if pd.notna(row["bundle_code"]):
        cost = bundle_costs.get(row["bundle_code"])
        if cost is not None:
            return float(cost), False
    
    # 3. Bebidas: usar costo esperado
    if any(kw in name for kw in DRINK_KEYWORDS):
        return expected_drink_cost, False
    
    # 4. Extra aguacate: costo fijo
    if "EXTRA AGUACATE" in name:
        return AVOCADO_COST, False
    
    # 5. Producto mapeado: buscar en product_costs
    if pd.notna(row["product_code"]):
        cost = product_costs.get(row["product_code"])
        if cost is not None:
            return float(cost), False
    
    # 6. FALLBACK: Costo estimado basado en margen objetivo
    # costo = precio * (1 - margen_objetivo)
    if row["cantidad"] > 0:
        unit_price = row["importe"] / row["cantidad"]
        estimated_cost = unit_price * COST_ESTIMATION_MULTIPLIER
        return estimated_cost, True
    
    # Edge case: cantidad = 0
    estimated_cost = row["importe"] * COST_ESTIMATION_MULTIPLIER
    return estimated_cost, True


# ============================================================
# CALCULOS FINANCIEROS
# ============================================================

def compute_financial_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula metricas financieras derivadas.
    Asume que unit_cost ya esta resuelto y nunca es NaN.
    """
    df = df.copy()
    
    # Costo total = unit_cost * quantity
    df["total_cost"] = df["unit_cost"] * df["cantidad"]
    
    # Margen bruto = revenue - costo total
    df["gross_margin"] = df["importe"] - df["total_cost"]
    
    # Margen bruto % = margen / revenue
    df["gross_margin_pct"] = np.where(
        df["importe"] > 0,
        df["gross_margin"] / df["importe"],
        0.0
    )
    
    return df


# ============================================================
# CONSTRUCCION DE OUTPUT
# ============================================================

def build_output_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Construye el DataFrame de salida con el schema contractual.
    Renombra columnas y fuerza tipos.
    """
    # Seleccionar y renombrar columnas
    output = df[[
        "sale_date",
        "descripcion",
        "product_code",
        "bundle_code",
        "cantidad",
        "importe",
        "unit_cost",
        "total_cost",
        "gross_margin",
        "gross_margin_pct",
        "cost_estimated",
        "non_product_revenue"
    ]].copy()
    
    output.columns = [
        "sale_date",
        "product_name",
        "product_code",
        "bundle_code",
        "quantity",
        "net_amount",
        "unit_cost",
        "total_cost",
        "gross_margin",
        "gross_margin_pct",
        "cost_estimated",
        "non_product_revenue"
    ]
    
    # Forzar tipos segun schema
    output["sale_date"] = pd.to_datetime(output["sale_date"])
    output["product_name"] = output["product_name"].astype(str)
    output["product_code"] = output["product_code"].astype(str)
    output["bundle_code"] = output["bundle_code"].astype(str)
    output["quantity"] = output["quantity"].astype(float)
    output["net_amount"] = output["net_amount"].astype(float)
    output["unit_cost"] = output["unit_cost"].astype(float)
    output["total_cost"] = output["total_cost"].astype(float)
    output["gross_margin"] = output["gross_margin"].astype(float)
    output["gross_margin_pct"] = output["gross_margin_pct"].astype(float)
    output["cost_estimated"] = output["cost_estimated"].astype(bool)
    output["non_product_revenue"] = output["non_product_revenue"].astype(bool)
    
    # Validar que unit_cost nunca sea NaN
    if output["unit_cost"].isna().any():
        raise ValueError("CRITICAL: unit_cost contains NaN values after resolution")
    
    return output


# ============================================================
# AUDITORIA
# ============================================================

def print_audit_summary(output: pd.DataFrame) -> None:
    """Imprime resumen de auditoria"""
    print("\n" + "=" * 60)
    print("AUDIT SUMMARY")
    print("=" * 60)
    
    print(f"\nTotal rows: {len(output):,}")
    print(f"Date range: {output['sale_date'].min().date()} -> {output['sale_date'].max().date()}")
    
    # Costos estimados
    estimated = output["cost_estimated"].sum()
    est_pct = (estimated / len(output) * 100) if len(output) > 0 else 0
    print(f"Estimated costs: {estimated:,} ({est_pct:.1f}%)")
    
    # Ingresos no operativos
    non_product = output["non_product_revenue"].sum()
    print(f"Non-product revenue items: {non_product:,}")
    
    # Metricas financieras
    total_margin = output["gross_margin"].sum()
    total_revenue = output["net_amount"].sum()
    avg_margin_pct = (total_margin / total_revenue * 100) if total_revenue > 0 else 0
    
    print(f"\nTotal gross margin: ${total_margin:,.0f}")
    print(f"Total revenue: ${total_revenue:,.0f}")
    print(f"Average margin %: {avg_margin_pct:.1f}%")
    
    # Productos con margen negativo
    neg_margin = output[output["gross_margin"] < 0]
    if len(neg_margin) > 0:
        neg_total = neg_margin.groupby("product_name")["gross_margin"].sum().sort_values()
        print(f"\nWARNING: {len(neg_margin):,} items with negative margin")
        print("Top 5 negative margin products:")
        print(neg_total.head(5))
    else:
        print("\nAll products have non-negative margins")
    
    # Distribucion de costos estimados por revenue
    if output["cost_estimated"].sum() > 0:
        est_revenue = output[output["cost_estimated"]]["net_amount"].sum()
        total_rev = output["net_amount"].sum()
        print(f"\nEstimated costs represent {est_revenue/total_rev*100:.1f}% of revenue")
    
    print("\n" + "=" * 60)


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("Building fact_sales_margin.parquet")
    print("=" * 60)
    
    # --------------------------------------------------------
    # 1. CARGA DE DATOS
    # --------------------------------------------------------
    print("\n[1/6] Loading data...")
    
    sales = pd.read_parquet(SALES_FILE)
    print(f"  - Sales: {len(sales):,} rows")
    
    # Mapeo de nombres
    mapping = pd.read_csv(MAPPING_FILE)
    mapping.columns = mapping.columns.str.strip()
    if "bundle_code" not in mapping.columns:
        mapping["bundle_code"] = None
    
    # Costos
    product_costs = load_cost_map(PRODUCT_COST_FILE, "product_code")
    bundle_costs = load_cost_map(BUNDLE_COST_FILE, "bundle_code")
    expected_drink_cost = load_expected_drink_cost()
    
    print(f"  - Product costs: {len(product_costs):,}")
    print(f"  - Bundle costs: {len(bundle_costs):,}")
    print(f"  - Expected drink cost: ${expected_drink_cost:.2f}")
    
    # --------------------------------------------------------
    # 2. NORMALIZACION Y MAPEO
    # --------------------------------------------------------
    print("\n[2/6] Normalizing and mapping products...")
    
    # Normalizar nombres
    sales["product_name_norm"] = sales["descripcion"].apply(normalize_text)
    mapping["raw_product_name_norm"] = mapping["raw_product_name"].apply(normalize_text)
    
    # Merge con mapping
    sales = sales.merge(
        mapping[["raw_product_name_norm", "product_code", "bundle_code"]],
        left_on="product_name_norm",
        right_on="raw_product_name_norm",
        how="left"
    )
    
    mapped_count = sales["product_code"].notna().sum()
    print(f"  - Mapped products: {mapped_count:,} / {len(sales):,} ({mapped_count/len(sales)*100:.1f}%)")
    
    # --------------------------------------------------------
    # 3. FLAGS DE CONTROL
    # --------------------------------------------------------
    print("\n[3/6] Setting control flags...")
    
    # Asegurar sale_date como datetime
    sales["sale_date"] = pd.to_datetime(sales["sale_date"])
    
    # Ingresos no operativos
    sales["non_product_revenue"] = sales["product_name_norm"].apply(
        lambda x: any(k in x for k in NON_PRODUCT_KEYWORDS)
    )
    
    non_product_count = sales["non_product_revenue"].sum()
    print(f"  - Non-product revenue items: {non_product_count:,}")
    
    # --------------------------------------------------------
    # 4. RESOLUCION DE COSTOS
    # --------------------------------------------------------
    print("\n[4/6] Resolving unit costs...")
    
    # Aplicar resolucion de costos
    sales[["unit_cost", "cost_estimated"]] = sales.apply(
        lambda row: resolve_unit_cost(row, product_costs, bundle_costs, expected_drink_cost),
        axis=1,
        result_type="expand"
    )
    
    # Estadisticas
    estimated = sales["cost_estimated"].sum()
    est_pct = (estimated / len(sales) * 100) if len(sales) > 0 else 0
    
    print(f"  - Total items: {len(sales):,}")
    print(f"  - Estimated costs: {estimated:,} ({est_pct:.1f}%)")
    
    # VALIDACION CRITICA: unit_cost nunca debe ser NaN
    if sales["unit_cost"].isna().any():
        nan_count = sales["unit_cost"].isna().sum()
        raise ValueError(f"CRITICAL ERROR: {nan_count} rows have NaN unit_cost after resolution")
    
    # --------------------------------------------------------
    # 5. CALCULOS FINANCIEROS
    # --------------------------------------------------------
    print("\n[5/6] Computing financial metrics...")
    
    sales = compute_financial_metrics(sales)
    
    total_margin = sales["gross_margin"].sum()
    total_revenue = sales["importe"].sum()
    avg_margin_pct = (total_margin / total_revenue * 100) if total_revenue > 0 else 0
    
    print(f"  - Total gross margin: ${total_margin:,.0f}")
    print(f"  - Average margin %: {avg_margin_pct:.1f}%")
    
    # --------------------------------------------------------
    # 6. CONSTRUCCION DEL OUTPUT
    # --------------------------------------------------------
    print("\n[6/6] Building output...")
    
    output = build_output_dataframe(sales)
    
    # Guardar
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    output.to_parquet(OUTPUT_FILE, index=False)
    
    print(f"\nWrote {OUTPUT_FILE}")
    print(f"Rows: {len(output):,}")
    print(f"Columns: {list(output.columns)}")
    
    # --------------------------------------------------------
    # AUDITORIA FINAL
    # --------------------------------------------------------
    print_audit_summary(output)
    
    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()