import pandas as pd
from pathlib import Path

SALES_FILE = Path("data/analytics/fact_sales_margin.parquet")
RECIPE_FILE = Path("data/processed_data/recipe_items.csv")
COST_FILE = Path("data/processed_data/dim_input_costs.csv")
OUTPUT_FILE = Path("data/analytics/cost_sensitivity_by_item.csv")

SCENARIOS = [0.05, 0.10]

def main():
    sales = pd.read_parquet(SALES_FILE)
    recipe = pd.read_csv(RECIPE_FILE)
    costs = pd.read_csv(COST_FILE)

    costs = costs[costs["active"] == 1].copy()

    results = []

    # Margen base por item
    base_margin = (
        sales
        .groupby("product_code", as_index=False)
        .agg(
            total_margin=("gross_margin", "sum"),
            total_units=("quantity", "sum")
        )
    )

    for _, cost in costs.iterrows():
        ingredient = cost["ingredient_name"]
        unit_cost = cost["unit_cost"]

        affected = recipe[recipe["ingredient_name"] == ingredient]
        if affected.empty:
            continue

        for _, row in affected.iterrows():
            product = row["product_code"]
            qty_per_unit = row["quantity"]

            product_sales = base_margin[
                base_margin["product_code"] == product
            ]

            if product_sales.empty:
                continue

            units_sold = product_sales["total_units"].iloc[0]
            base_product_margin = product_sales["total_margin"].iloc[0]

            for pct in SCENARIOS:
                delta_cost = unit_cost * pct * qty_per_unit * units_sold
                scenario_margin = base_product_margin - delta_cost

                results.append({
                    "ingredient_name": ingredient,
                    "product_code": product,
                    "cost_increase_pct": pct,
                    "base_margin": base_product_margin,
                    "scenario_margin": scenario_margin,
                    "margin_delta_abs": scenario_margin - base_product_margin,
                    "margin_delta_pct": (
                        (scenario_margin - base_product_margin)
                        / base_product_margin
                        if base_product_margin != 0 else None
                    )
                })

    pd.DataFrame(results).to_csv(OUTPUT_FILE, index=False)
    print(f"Wrote cost_sensitivity_by_item.csv ({len(results)} rows)")

if __name__ == "__main__":
    main()
