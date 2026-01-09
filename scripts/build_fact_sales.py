import pandas as pd
import hashlib
from pathlib import Path

RAW_FILE = Path("data/analytics/fact_sales_raw.parquet")
OUTPUT_FILE = Path("data/analytics/fact_sales.parquet")

BUSINESS_ID = "astro_burger"


def parse_discount(value):
    if pd.isna(value):
        return 0.0
    if isinstance(value, str) and "%" in value:
        return float(value.replace("%", "")) / 100
    return 0.0


def make_sale_id(row):
    raw = (
        f"{BUSINESS_ID}|{row['ticket_id']}|{row['ticket_order']}|"
        f"{row['sale_datetime']}|{row['product_name']}|"
        f"{row['quantity']}|{row['gross_amount']}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def main():
    print("Loading fact_sales_raw.parquet...")
    df = pd.read_parquet(RAW_FILE)

    # Renombrar columnas
    df = df.rename(
        columns={
            "foliocuenta": "ticket_id",
            "orden": "ticket_order",
            "descripcion": "product_name",
            "importe": "gross_amount",
            "fechaapertura": "sale_datetime",
        }
    )

    # Fechas
    df["sale_datetime"] = pd.to_datetime(df["sale_datetime"])
    df["sale_date"] = df["sale_datetime"].dt.date

    # Tipos
    df["quantity"] = df["cantidad"].astype(float)
    df["gross_amount"] = df["gross_amount"].astype(float)

    # Descuento
    df["discount_pct"] = df["descuento"].apply(parse_discount)
    df["net_amount"] = df["gross_amount"] * (1 - df["discount_pct"])

    # Metadata
    df["business_id"] = BUSINESS_ID

    if "source" not in df.columns:
        df["source"] = "historical_parquet"

    # Sale ID
    print("Generating sale_id...")
    df["sale_id"] = df.apply(make_sale_id, axis=1)

    final_cols = [
        "sale_id",
        "business_id",
        "sale_date",
        "sale_datetime",
        "ticket_id",
        "ticket_order",
        "product_name",
        "quantity",
        "gross_amount",
        "discount_pct",
        "net_amount",
        "source",
    ]

    df_final = df[final_cols].sort_values("sale_datetime")

    print(f"Writing fact_sales.parquet ({len(df_final):,} rows)")
    df_final.to_parquet(OUTPUT_FILE, index=False)
    print("Done.")


if __name__ == "__main__":
    main()
