import pandas as pd
from pathlib import Path

# =========================
# Paths
# =========================
SALES_FILE = Path("data/analytics/fact_sales_margin.parquet")
RECIPE_FILE = Path("data/processed_data/recipe_items.csv")
COST_FILE = Path("data/processed_data/dim_input_costs.csv")
OUTPUT_FILE = Path("data/analytics/cost_sensitivity.csv")

# Escenarios de sensibilidad
SCENARIOS = [0.05, 0.10]  # +5%, +10%

def main():
    # -------------------------------------------------
    # Load data
    # -------------------------------------------------
    sales = pd.read_parquet(SALES_FILE)
    recipe = pd.read_csv(RECIPE_FILE)
    costs = pd.read_csv(COST_FILE)

    # Solo insumos activos
    costs = costs[costs["active"] == 1].copy()

    baseline_margin = sales["gross_margin"].sum()

    results = []

    # -------------------------------------------------
    # Sensitivity analysis per ingredient
    # -------------------------------------------------
    for _, cost in costs.iterrows():
        ingredient = cost["ingredient_name"]
        unit_cost = cost["unit_cost"]

        # Productos que usan este insumo
        affected_recipes = recipe[recipe["ingredient_name"] == ingredient]

        if affected_recipes.empty:
            continue

        affected_products = affected_recipes["product_code"].unique()

        affected_sales = sales[
            sales["product_code"].isin(affected_products)
        ]

        if affected_sales.empty:
            continue

        total_units = affected_sales["quantity"].sum()

        for pct in SCENARIOS:
            delta_total_cost = total_units * unit_cost * pct
            scenario_margin = baseline_margin - delta_total_cost

            results.append({
                "ingredient_name": ingredient,
                "cost_increase_pct": pct,
                "baseline_margin": baseline_margin,
                "scenario_margin": scenario_margin,
                "margin_delta_abs": scenario_margin - baseline_margin,
                "margin_delta_pct": (scenario_margin - baseline_margin) / baseline_margin
            })

    pd.DataFrame(results).to_csv(OUTPUT_FILE, index=False)
    print(f"Wrote cost_sensitivity.csv ({len(results)} scenarios)")

if __name__ == "__main__":
    main()
