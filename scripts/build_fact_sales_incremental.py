import pandas as pd
from pathlib import Path

HISTORICAL_FILE = Path("data/analytics/fact_sales_raw.parquet")
NEW_POS_FILE = Path("data/raw_data/comandas.xlsx")
OUTPUT_FILE = HISTORICAL_FILE


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
    print("Loading historical sales...")
    historical = pd.read_parquet(HISTORICAL_FILE)

    historical["sale_date"] = pd.to_datetime(historical["sale_date"])
    last_date = historical["sale_date"].max().date()

    print(f"Last loaded sale_date: {last_date}")

    print("Loading new POS file...")
    new = pd.read_excel(NEW_POS_FILE)

    missing = set(EXPECTED_COLUMNS) - set(new.columns)
    if missing:
        raise ValueError(f"Missing columns in comandas.xlsx: {missing}")

    new = new[EXPECTED_COLUMNS].copy()

    # Cast string columns to match historical parquet schema
    for col in ["foliocomanda", "foliocuenta", "orden", "mesero", "claveproducto", "descripcion"]:
        new[col] = new[col].astype(str)
    for col in ["cantidad", "descuento", "importe"]:
        new[col] = pd.to_numeric(new[col], errors="coerce")

    new["fechaapertura"] = pd.to_datetime(new["fechaapertura"], errors="coerce")
    new = new[new["fechaapertura"].notna()]

    new["sale_datetime"] = new["fechaapertura"]
    new["sale_date"] = new["sale_datetime"].dt.date

    # Solo fechas nuevas
    new = new[new["sale_date"] > last_date].copy()

    if new.empty:
        print("No new days detected. Nothing to add.")
        return

    min_new = new["sale_date"].min()
    max_new = new["sale_date"].max()

    print(f"New days detected: {min_new} -> {max_new}")

    # Append
    combined = pd.concat([historical, new], ignore_index=True)

    # --- Normalize sale_date to Timestamp ---
    combined["sale_date"] = pd.to_datetime(combined["sale_date"])


    # Ordenar para estabilidad
    combined = combined.sort_values(
        ["sale_date", "foliocuenta", "orden"]
    )

    combined.to_parquet(OUTPUT_FILE, index=False)

    print(
        f"Updated fact_sales_raw.parquet "
        f"({len(combined):,} rows)"
    )


if __name__ == "__main__":
    main()
