import pandas as pd
from pathlib import Path

INPUT_FILE = Path("data/analytics/fact_sales_margin.parquet")
OUTPUT_FILE = Path("data/analytics/margin_summary.csv")


def main():
    sales = pd.read_parquet(INPUT_FILE)

    # Solo ventas con costos válidos
    sales = sales[sales["cost_applicable"]].copy()

    # Excluir ingresos no operativos
    sales = sales[~sales["non_product_revenue"]]

    summary = (
        sales
        .groupby(["product_code", "bundle_code"], dropna=False)
        .agg(
            total_sales=("importe", "sum"),
            total_units=("cantidad", "sum"),
            total_cost=("total_cost", "sum"),
            gross_margin=("gross_margin", "sum"),
        )
        .reset_index()
    )

    summary["gross_margin_pct"] = summary["gross_margin"] / summary["total_sales"]

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUTPUT_FILE, index=False)

    print(f"Wrote margin_summary.csv ({len(summary)} items)")


if __name__ == "__main__":
    main()
