import pandas as pd
from pathlib import Path

INPUT_FILE = Path("data/analytics/fact_sales_margin.parquet")
OUTPUT_FILE = Path("data/analytics/margin_summary.csv")


def main():
    df = pd.read_parquet(INPUT_FILE)

    # Unificar producto y paquete como item vendible
    df["item_code"] = df["bundle_code"].fillna(df["product_code"])

    # Agregación
    summary = (
        df.groupby("item_code")
        .agg(
            total_units_sold=("quantity", "sum"),
            total_revenue=("net_amount", "sum"),
            total_cost=("total_cost", "sum"),
            total_margin=("gross_margin", "sum"),
            avg_margin_pct=("gross_margin_pct", "mean"),
        )
        .reset_index()
    )

    # Shares
    summary["share_of_revenue"] = summary["total_revenue"] / summary["total_revenue"].sum()
    summary["share_of_margin"] = summary["total_margin"] / summary["total_margin"].sum()

    # Orden por impacto
    summary = summary.sort_values("total_margin", ascending=False)

    summary.to_csv(OUTPUT_FILE, index=False)
    print(f"Wrote margin_summary.csv ({len(summary)} items)")


if __name__ == "__main__":
    main()
