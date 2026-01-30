"""
Build fact_sales_raw.parquet
=============================
ETL para consolidar archivos POS históricos en un parquet tipado.

Este script NO contiene lógica de negocio.
Solo carga, valida schema, normaliza tipos y consolida.

Schema de salida (CONTRATO):
- foliocomanda: str
- foliocuenta: str
- orden: str
- fechaapertura: datetime64[ns]
- fechacierre: datetime64[ns]
- mesero: str
- claveproducto: str
- descripcion: str
- cantidad: float
- descuento: float
- importe: float
- source_file: str
- sale_datetime: datetime64[ns]
- sale_date: datetime64[ns]
- year: int
"""

import pandas as pd
from pathlib import Path
from typing import List


# ============================================================
# CONFIGURACION
# ============================================================

RAW_POS_DIR = Path("data/raw_data/POS")
OUTPUT_FILE = Path("data/analytics/fact_sales_raw.parquet")

# Columnas esperadas en archivos de entrada
INPUT_COLUMNS = [
    "foliocomanda",
    "foliocuenta",
    "orden",
    "fechaapertura",
    "fechacierre",
    "mesero",
    "claveproducto",
    "descripcion",
    "cantidad",
    "descuento",
    "importe",
]

# Schema estricto del output
OUTPUT_SCHEMA = {
    "foliocomanda": "str",
    "foliocuenta": "str",
    "orden": "str",
    "fechaapertura": "datetime64[ns]",
    "fechacierre": "datetime64[ns]",
    "mesero": "str",
    "claveproducto": "str",
    "descripcion": "str",
    "cantidad": "float64",
    "descuento": "float64",
    "importe": "float64",
    "source_file": "str",
    "sale_datetime": "datetime64[ns]",
    "sale_date": "datetime64[ns]",
    "year": "int64",
}


# ============================================================
# FUNCIONES
# ============================================================

def validate_input_schema(df: pd.DataFrame, filename: str) -> None:
    """
    Valida que el DataFrame tenga todas las columnas esperadas.
    Falla explícitamente si falta alguna.
    """
    missing = set(INPUT_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Schema validation failed for {filename}: missing columns {missing}")


def normalize_types(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza tipos de datos según el contrato.
    No aplica lógica de negocio, solo conversiones de tipo.
    """
    df = df.copy()
    
    # Fechas a datetime64[ns]
    df["fechaapertura"] = pd.to_datetime(df["fechaapertura"], errors="coerce")
    df["fechacierre"] = pd.to_datetime(df["fechacierre"], errors="coerce")
    
    # Numéricos a float64
    df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce")
    df["descuento"] = pd.to_numeric(df["descuento"], errors="coerce")
    df["importe"] = pd.to_numeric(df["importe"], errors="coerce")
    
    # Strings (asegurar tipo object para compatibilidad)
    for col in ["foliocomanda", "foliocuenta", "orden", "mesero", "claveproducto", "descripcion"]:
        df[col] = df[col].astype(str)
    
    return df


def add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega columnas derivadas estándar.
    Son transformaciones directas sin lógica de negocio.
    """
    df = df.copy()
    
    # sale_datetime es alias directo de fechaapertura
    df["sale_datetime"] = df["fechaapertura"]
    
    # sale_date es solo la fecha (sin hora)
    df["sale_date"] = df["sale_datetime"].dt.normalize()
    
    # year extraído de sale_datetime
    df["year"] = df["sale_datetime"].dt.year
    
    return df


def enforce_output_schema(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fuerza el schema exacto del output.
    Falla si hay inconsistencias.
    """
    # Verificar que todas las columnas del schema existen
    missing = set(OUTPUT_SCHEMA.keys()) - set(df.columns)
    if missing:
        raise ValueError(f"Output schema validation failed: missing columns {missing}")
    
    # Seleccionar solo columnas del contrato (en orden)
    df = df[list(OUTPUT_SCHEMA.keys())].copy()
    
    # Forzar tipos
    for col, dtype in OUTPUT_SCHEMA.items():
        if dtype == "str":
            df[col] = df[col].astype(str)
        elif dtype == "float64":
            df[col] = df[col].astype(float)
        elif dtype == "int64":
            df[col] = df[col].astype("Int64")  # Nullable integer
        elif dtype == "datetime64[ns]":
            df[col] = pd.to_datetime(df[col])
    
    return df


def load_pos_files() -> List[pd.DataFrame]:
    """
    Carga todos los archivos Excel del directorio POS.
    Valida schema de cada uno.
    """
    files = sorted(RAW_POS_DIR.glob("*.xlsx"))
    
    if not files:
        raise ValueError(f"No Excel files found in {RAW_POS_DIR}")
    
    dfs = []
    
    for f in files:
        print(f"Loading {f.name}")
        
        # Cargar
        df = pd.read_excel(f)
        
        # Validar schema
        validate_input_schema(df, f.name)
        
        # Seleccionar solo columnas esperadas
        df = df[INPUT_COLUMNS].copy()
        
        # Normalizar tipos
        df = normalize_types(df)
        
        # Agregar metadata
        df["source_file"] = f.name
        
        dfs.append(df)
    
    return dfs


def print_audit_summary(df: pd.DataFrame) -> None:
    """
    Imprime resumen de auditoría básica.
    No modifica los datos.
    """
    print("\n=== AUDIT SUMMARY ===")
    print(f"Total rows: {len(df):,}")
    print(f"Date range: {df['sale_date'].min()} -> {df['sale_date'].max()}")
    print(f"Unique days: {df['sale_date'].nunique():,}")
    
    # Resumen por año
    sales_by_year = df.groupby("year")["importe"].sum()
    days_by_year = df.groupby("year")["sale_date"].nunique()
    
    audit = pd.DataFrame({
        "total_sales": sales_by_year,
        "days_with_sales": days_by_year,
        "avg_daily_sales": sales_by_year / days_by_year
    })
    
    print("\nSales by year:")
    print(audit.round(2))


# ============================================================
# MAIN
# ============================================================

def main():
    print("Starting POS historical rebuild...\n")
    
    # 1. Cargar archivos
    dfs = load_pos_files()
    
    # 2. Consolidar
    sales = pd.concat(dfs, ignore_index=True)
    print(f"\nConsolidated {len(sales):,} rows from {len(dfs)} files")
    
    # 3. Agregar columnas derivadas
    sales = add_derived_columns(sales)
    
    # 4. Forzar schema de salida
    sales = enforce_output_schema(sales)
    
    # 5. Auditoría
    print_audit_summary(sales)
    
    # 6. Guardar
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    sales.to_parquet(OUTPUT_FILE, index=False)
    
    print(f"\nWrote {OUTPUT_FILE} ({len(sales):,} rows)")
    print(f"Schema: {list(sales.dtypes.items())}")


if __name__ == "__main__":
    main()
