import pandas as pd
from pathlib import Path

RAW_POS_DIR = Path("data/raw_data/POS")
OUTPUT_FILE = Path("data/analytics/fact_sales_raw.parquet")

EXPECTED_COLUMNS = [
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

def main():
    print("Starting POS historical rebuild...\n")

    files = sorted(RAW_POS_DIR.glob("*.xlsx"))
    if not files:
        raise ValueError("No Excel files found in data/raw_data/POS")

    dfs = []

    for f in files:
        print(f"Loading {f.name}")
        df = pd.read_excel(f)

        # Validar columnas
        missing = set(EXPECTED_COLUMNS) - set(df.columns)
        if missing:
            raise ValueError(f"{f.name} missing columns: {missing}")

        df = df[EXPECTED_COLUMNS].copy()

        # Normalizar tipos
        df["fechaapertura"] = pd.to_datetime(df["fechaapertura"], errors="coerce")
        df["fechacierre"] = pd.to_datetime(df["fechacierre"], errors="coerce")
        df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(0)
        df["importe"] = pd.to_numeric(df["importe"], errors="coerce").fillna(0.0)

        # Metadata
        df["source_file"] = f.name

        dfs.append(df)

    sales = pd.concat(dfs, ignore_index=True)

    # Eliminar filas claramente inválidas
    sales = sales[
        sales["fechaapertura"].notna() &
        (sales["importe"] != 0)
    ].copy()

    # Crear columnas estándar
    sales["sale_datetime"] = sales["fechaapertura"]
    sales["sale_date"] = sales["sale_datetime"].dt.date
    sales["year"] = sales["sale_datetime"].dt.year

    # =============================
    # AUDITORÍA BÁSICA
    # =============================
    print("\n=== AUDIT SUMMARY ===")
    print(f"Rows: {len(sales):,}")
    print(f"Date range: {sales['sale_date'].min()} → {sales['sale_date'].max()}")
    print(f"Unique days: {sales['sale_date'].nunique():,}")

    sales_by_year = sales.groupby("year")["importe"].sum()
    days_by_year = sales.groupby("year")["sale_date"].nunique()

    audit = pd.DataFrame({
        "total_sales": sales_by_year,
        "days_with_sales": days_by_year,
        "avg_daily_sales": sales_by_year / days_by_year
    })

    print("\nSales by year:")
    print(audit.round(2))

    # =============================
    # GUARDAR
    # =============================
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    sales.to_parquet(OUTPUT_FILE, index=False)

    print(f"\n✓ Wrote {OUTPUT_FILE} ({len(sales):,} rows)")

if __name__ == "__main__":
    main()
