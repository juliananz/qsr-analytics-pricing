import pandas as pd
from pathlib import Path

# -------------------------------------------------
# Files
# -------------------------------------------------
SALES_FILE = Path("data/analytics/fact_sales_margin.parquet")
RECIPE_FILE = Path("data/processed_data/recipe_items.csv")
COST_FILE = Path("data/processed_data/dim_input_costs.csv")
BUNDLE_FILE = Path("data/processed_data/bundle_components.csv")
OUTPUT_FILE = Path("data/analytics/cost_sensitivity_full.csv")

# Escenarios de sensibilidad
SCENARIOS = [0.05, 0.10]


def main():
    # -------------------------------------------------
    # Load data
    # -------------------------------------------------
    sales = pd.read_parquet(SALES_FILE)
    recipe = pd.read_csv(RECIPE_FILE)
    costs = pd.read_csv(COST_FILE)
    bundles = pd.read_csv(BUNDLE_FILE)

    # -------------------------------------------------
    # Defensive filters
    # -------------------------------------------------
    recipe = recipe[recipe["active"] == 1].copy()
    costs = costs[costs["active"] == 1].copy()
    bundles = bundles[bundles["active"] == 1].copy()

    # -------------------------------------------------
    # Base sales by product
    # -------------------------------------------------
    product_sales = (
        sales
        .groupby("product_code", as_index=False)
        .agg(
            units_sold=("quantity", "sum"),
            base_margin=("gross_margin", "sum")
        )
    )

    # -------------------------------------------------
    # Base sales by bundle
    # -------------------------------------------------
    bundle_sales = (
        sales
        .dropna(subset=["bundle_code"])
        .groupby("bundle_code", as_index=False)
        .agg(
            bundle_units=("quantity", "sum"),
            base_margin=("gross_margin", "sum")
        )
    )

    results = []

    # =================================================
    # NIVEL 1 — PRODUCTOS INDIVIDUALES
    # =================================================
    for _, cost in costs.iterrows():
        ingredient = cost["ingredient_name"]
        unit_cost = cost["unit_cost"]

        affected_products = recipe[recipe["ingredient_name"] == ingredient]

        if affected_products.empty:
            continue

        for _, r in affected_products.iterrows():
            product = r["product_code"]
            qty_per_unit = r["quantity"]

            ps = product_sales[product_sales["product_code"] == product]
            if ps.empty:
                continue

            units = ps["units_sold"].iloc[0]
            base_margin = ps["base_margin"].iloc[0]

            for s in SCENARIOS:
                delta_cost = unit_cost * s * qty_per_unit * units

                results.append({
                    "level": "product",
                    "ingredient_name": ingredient,
                    "item_code": product,
                    "scenario_pct": s,
                    "base_margin": base_margin,
                    "scenario_margin": base_margin - delta_cost,
                    "margin_delta_abs": -delta_cost
                })

    # =================================================
    # NIVEL 2 — PAQUETES
    # =================================================
    for _, cost in costs.iterrows():
        ingredient = cost["ingredient_name"]
        unit_cost = cost["unit_cost"]

        affected_products = recipe[recipe["ingredient_name"] == ingredient]
        if affected_products.empty:
            continue

        for _, bc in bundles.iterrows():
            bundle = bc["bundle_code"]
            component = bc["component_code"]
            component_qty = bc["quantity"]

            # El ingrediente no afecta este componente
            if component not in affected_products["product_code"].values:
                continue

            recipe_row = affected_products[
                affected_products["product_code"] == component
            ]

            qty_per_unit = recipe_row["quantity"].iloc[0]

            bs = bundle_sales[bundle_sales["bundle_code"] == bundle]
            if bs.empty:
                continue

            bundle_units = bs["bundle_units"].iloc[0]
            base_margin = bs["base_margin"].iloc[0]

            for s in SCENARIOS:
                delta_cost = (
                    unit_cost
                    * s
                    * qty_per_unit
                    * component_qty
                    * bundle_units
                )

                results.append({
                    "level": "bundle",
                    "ingredient_name": ingredient,
                    "item_code": bundle,
                    "scenario_pct": s,
                    "base_margin": base_margin,
                    "scenario_margin": base_margin - delta_cost,
                    "margin_delta_abs": -delta_cost
                })

    # -------------------------------------------------
    # Output
    # -------------------------------------------------
    df = pd.DataFrame(results)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"Wrote cost_sensitivity_full.csv ({len(df):,} rows)")


if __name__ == "__main__":
    main()
