import pandas as pd
import numpy as np
from pathlib import Path

SALES_FILE = Path("data/analytics/fact_sales.parquet")
PRODUCT_COST_FILE = Path("data/processed_data/product_unit_cost.csv")
BUNDLE_COST_FILE = Path("data/processed_data/bundle_unit_cost.csv")
MAPPING_FILE = Path("data/processed_data/product_name_mapping.csv")
EXPECTED_DRINK_COST_FILE = Path("data/processed_data/expected_drink_cost.csv")
OUTPUT_FILE = Path("data/analytics/fact_sales_margin.parquet")

# -------------------------------------------------
# Configuración explícita
# -------------------------------------------------
NON_PRODUCT_KEYWORDS = [
    "ENVIO", "EXCESO", "AJUSTE", "EFECTIVO", "$"
]

AVOCADO_COST = 5.0


def main():
    # -------------------------------------------------
    # Load base data
    # -------------------------------------------------
    sales = pd.read_parquet(SALES_FILE)

    mapping = pd.read_csv(MAPPING_FILE)
    mapping.columns = mapping.columns.str.strip()

    product_cost = pd.read_csv(PRODUCT_COST_FILE)
    bundle_cost = pd.read_csv(BUNDLE_COST_FILE)
    drink_cost = pd.read_csv(EXPECTED_DRINK_COST_FILE)

    # -------------------------------------------------
    # Expected drink cost (EXPLÍCITO)
    # -------------------------------------------------
    if "expected_unit_cost" not in drink_cost.columns:
        raise ValueError(
            "expected_drink_cost.csv must contain column 'expected_unit_cost'"
        )

    # Se asume un solo costo esperado global
    expected_drink_cost = float(drink_cost["expected_unit_cost"].iloc[0])

    # -------------------------------------------------
    # Defensive mapping setup
    # -------------------------------------------------
    if "bundle_code" not in mapping.columns:
        mapping["bundle_code"] = None

    # -------------------------------------------------
    # Mapear productos
    # -------------------------------------------------
    sales = sales.merge(
        mapping[["raw_product_name", "product_code", "bundle_code"]],
        left_on="product_name",
        right_on="raw_product_name",
        how="left"
    )

    # -------------------------------------------------
    # Identificar no-productos (envíos, ajustes, etc.)
    # -------------------------------------------------
    sales["non_product_revenue"] = sales["product_name"].str.upper().apply(
        lambda x: any(k in x for k in NON_PRODUCT_KEYWORDS)
    )

    # -------------------------------------------------
    # Costos base
    # -------------------------------------------------
    product_cost_map = (
        product_cost
        .set_index("product_code")["unit_cost"]
        .to_dict()
    )

    bundle_cost_map = (
        bundle_cost
        .set_index("bundle_code")["unit_cost"]
        .to_dict()
    )

    # -------------------------------------------------
    # Resolver costo unitario
    # -------------------------------------------------
    def resolve_unit_cost(row):
        name = str(row["product_name"]).upper()

        # No-productos
        if row["non_product_revenue"]:
            return 0.0

        # Bundles
        if pd.notna(row["bundle_code"]):
            return bundle_cost_map.get(row["bundle_code"])

        # Bebidas (costo esperado)
        if (
            "REFRESCO" in name
            or "COCA" in name
            or "FANTA" in name
            or "SPRITE" in name
            or "FUZE" in name
            or "AGUA" in name
        ):
            return expected_drink_cost

        # Extra aguacate
        if "EXTRA AGUACATE" in name:
            return AVOCADO_COST

        # Producto individual
        return product_cost_map.get(row["product_code"])

    sales["unit_cost"] = sales.apply(resolve_unit_cost, axis=1)

    # -------------------------------------------------
    # Flags de calidad de costo
    # -------------------------------------------------
    sales["cost_estimated"] = sales["unit_cost"].isna()

    # Para los que aún no tienen costo, asumimos 0 pero marcamos
    sales["unit_cost"] = sales["unit_cost"].fillna(0.0)

    # -------------------------------------------------
    # Cálculos
    # -------------------------------------------------
    sales["total_cost"] = sales["unit_cost"] * sales["quantity"]
    sales["gross_margin"] = sales["net_amount"] - sales["total_cost"]

    sales["gross_margin_pct"] = np.where(
        sales["net_amount"] > 0,
        sales["gross_margin"] / sales["net_amount"],
        np.nan
    )

    # -------------------------------------------------
    # Output
    # -------------------------------------------------
    cols = [
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

    sales[cols].to_parquet(OUTPUT_FILE, index=False)
    print(f"Wrote fact_sales_margin.parquet ({len(sales):,} rows)")


if __name__ == "__main__":
    main()

