import pandas as pd
from pathlib import Path
import numpy as np

SALES_FILE = Path("data/analytics/fact_sales.parquet")
MAPPING_FILE = Path("data/processed_data/product_name_mapping.csv")
COST_FILE = Path("data/processed_data/product_unit_cost.csv")
OUTPUT_FILE = Path("data/analytics/sales_with_margin.parquet")


def main():
    sales = pd.read_parquet(SALES_FILE)
    mapping = pd.read_csv(MAPPING_FILE)
    mapping.columns = mapping.columns.str.strip()
    costs = pd.read_csv(COST_FILE)

    # Join ventas → product_code
    sales = sales.merge(
        mapping[["raw_product_name", "product_code"]],
        left_on="product_name",
        right_on="raw_product_name",
        how="left",
    )

    # Filtrar solo ventas mapeadas
    sales = sales[~sales["product_code"].isna()].copy()

    # Join costos
    sales = sales.merge(
        costs[["product_code", "unit_cost", "cost_confidence"]],
        on="product_code",
        how="left",
    )

    # Filtrar productos sin costo (ej. soda)
    sales = sales[~sales["unit_cost"].isna()].copy()

    # Cálculos
    sales["total_cost"] = sales["unit_cost"] * sales["quantity"]
    sales["gross_margin"] = sales["net_amount"] - sales["total_cost"]
    sales["gross_margin_pct"] = np.where(
        sales["net_amount"] > 0,
        sales["gross_margin"] / sales["net_amount"],
        np.nan
    )

    result_cols = [
        "sale_id",
        "sale_date",
        "product_code",
        "quantity",
        "net_amount",
        "unit_cost",
        "total_cost",
        "gross_margin",
        "gross_margin_pct",
        "cost_confidence",
    ]

    sales[result_cols].to_parquet(OUTPUT_FILE, index=False)
    print(f"Wrote sales_with_margin.parquet ({len(sales):,} rows)")


if __name__ == "__main__":
    main()
