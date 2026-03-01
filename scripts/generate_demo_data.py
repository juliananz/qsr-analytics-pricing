"""
generate_demo_data.py
=====================
Generates anonymised demo data from fact_sales_margin.parquet by:
  - Dividing all monetary columns by 20
  - Applying small random noise (±3%) to each monetary value
  - Preserving dates, product names, ratios, booleans, and quantities exactly

Output: data/demo/fact_sales_margin.parquet
"""

import random
from pathlib import Path

import pandas as pd

SRC = Path("data/analytics/fact_sales_margin.parquet")
DST = Path("data/demo/fact_sales_margin.parquet")

MONETARY_COLS = [
    "net_amount",
    "unit_cost",
    "total_cost",
    "gross_margin",
    "ventas_efectivo",
    "ventas_tarjeta",
    "ventas_app",
    "gastos_caja",
    "ventas_sistema",
    "total_gastos_dia",
]


def add_noise(value: float) -> float:
    if pd.isna(value):
        return value
    return value * random.uniform(0.97, 1.03)


def main() -> None:
    print(f"Reading {SRC} ...")
    df = pd.read_parquet(SRC)
    print(f"  {len(df):,} rows, {len(df.columns)} columns")

    present = [c for c in MONETARY_COLS if c in df.columns]
    missing = [c for c in MONETARY_COLS if c not in df.columns]
    if missing:
        print(f"  Warning: columns not found, skipping: {missing}")

    print("Applying transformations ...")
    for col in present:
        df[col] = (df[col] / 20).apply(add_noise).round(2)

    DST.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(DST, index=False)
    print(f"Saved: {DST}  ({DST.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
