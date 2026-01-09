import pandas as pd
from pathlib import Path

COSTS_FILE = Path("data/processed_data/dim_input_costs.csv")
RECIPES_FILE = Path("data/processed_data/recipe_items.csv")
PRODUCTS_FILE = Path("data/processed_data/dim_product.csv")
OUTPUT_FILE = Path("data/processed_data/product_unit_cost.csv")


def main():
    costs = pd.read_csv(COSTS_FILE)
    recipes = pd.read_csv(RECIPES_FILE)
    products = pd.read_csv(PRODUCTS_FILE)

    # Mapa de costos unitarios por insumo
    cost_map = costs.set_index("ingredient_name")[
        ["unit_cost", "cost_confidence"]
    ]

    rows = []

    # 1. Productos con receta
    for product_code, group in recipes.groupby("product_code"):
        total_cost = 0.0
        confidences = []

        for _, row in group.iterrows():
            ingredient = row["ingredient_name"]
            qty = row["quantity"]

            if ingredient not in cost_map.index:
                raise ValueError(f"Missing cost for ingredient: {ingredient}")

            ingredient_cost = cost_map.loc[ingredient, "unit_cost"]
            ingredient_conf = cost_map.loc[ingredient, "cost_confidence"]

            total_cost += ingredient_cost * qty
            confidences.append(ingredient_conf)

        cost_conf = "high" if all(c == "high" for c in confidences) else "low"

        rows.append(
            {
                "product_code": product_code,
                "unit_cost": round(total_cost, 2),
                "cost_confidence": cost_conf,
                "source": "recipe",
            }
        )

    # 2. Productos sin receta (direct cost)
    products_with_recipe = set(recipes["product_code"])
    all_products = set(products["product_code"])

    no_recipe_products = all_products - products_with_recipe

    for product_code in no_recipe_products:
        # buscar si existe como insumo directo
        cost_row = costs[costs["ingredient_name"] == product_code]

        if cost_row.empty:
            # no todos los productos requieren costo (ej. soda se verá después)
            continue

        rows.append(
            {
                "product_code": product_code,
                "unit_cost": float(cost_row["unit_cost"].iloc[0]),
                "cost_confidence": cost_row["cost_confidence"].iloc[0],
                "source": "direct_cost",
            }
        )

    result = pd.DataFrame(rows).sort_values("product_code")
    result.to_csv(OUTPUT_FILE, index=False)

    print(f"Wrote product_unit_cost.csv with {len(result)} rows")


if __name__ == "__main__":
    main()
