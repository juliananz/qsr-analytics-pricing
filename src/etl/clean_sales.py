import pandas as pd
from pathlib import Path
import hashlib

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
BUSINESS_ID = "astro_burger"


def parse_discount(value):
    if pd.isna(value):
        return 0.0
    if isinstance(value, str) and "%" in value:
        return float(value.replace("%", "")) / 100
    return 0.0


def make_sale_id(row):
    raw = (
        f"{BUSINESS_ID}|{row['foliocuenta']}|{row['orden']}|"
        f"{row['sale_datetime']}|{row['product_name']}|"
        f"{row['quantity']}|{row['gross_amount']}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def clean_sales_file(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)

    df = df.rename(
        columns={
            "descripcion": "product_name",
            "importe": "gross_amount",
            "fechaapertura": "sale_datetime",
        }
    )

    df["sale_datetime"] = pd.to_datetime(df["sale_datetime"])
    df["sale_date"] = df["sale_datetime"].dt.date
    df["quantity"] = df["cantidad"].astype(float)
    df["discount_pct"] = df["descuento"].apply(parse_discount)
    df["net_amount"] = df["gross_amount"] * (1 - df["discount_pct"])
    df["business_id"] = BUSINESS_ID

    df["sale_id"] = df.apply(make_sale_id, axis=1)

    df["source_file"] = path.name

    return df[
        [
            "sale_id",
            "business_id",
            "sale_date",
            "sale_datetime",
            "foliocuenta",
            "orden",
            "product_name",
            "quantity",
            "gross_amount",
            "discount_pct",
            "net_amount",
            "source_file",
        ]
    ]


if __name__ == "__main__":
    frames = []
    for file in RAW_DIR.glob("*.parquet"):
        frames.append(clean_sales_file(file))

    final = pd.concat(frames, ignore_index=True)
    PROCESSED_DIR.mkdir(exist_ok=True)
    final.to_parquet(PROCESSED_DIR / "sales_clean.parquet", index=False)
