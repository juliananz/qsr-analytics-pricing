import pandas as pd
from pathlib import Path

RECIPE_FILE = Path("data/processed_data/recipe_items.csv")
INPUT_COST_FILE = Path("data/processed_data/dim_input_costs.csv")
OUTPUT_FILE = Path("data/processed_data/product_unit_cost.csv")

# Proxies explícitos
AVOCADO_COST = 5.0
CHEESE_BAR_PORTIONS = 8  # 1 barra rinde 8 porciones

def main():
    recipes = pd.read_csv(RECIPE_FILE)
    inputs = pd.read_csv(INPUT_COST_FILE)

    # Normalización básica
    recipes["ingredient_name"] = recipes["ingredient_name"].str.strip()
    inputs["ingredient_name"] = inputs["ingredient_name"].str.strip()

    # Mapa de costos por ingrediente
    ingredient_cost_map = (
        inputs[inputs["active"] == 1]
        .set_index("ingredient_name")["unit_cost"]
        .to_dict()
    )

    rows = []
    audit = []

    for product_code, grp in recipes[recipes["active"] == 1].groupby("product_code"):
        total_cost = 0.0
        ok = True

        for _, r in grp.iterrows():
            ing = r["ingredient_name"]
            qty = float(r["quantity"])

            if ing == "Aguacate":
                unit_cost = AVOCADO_COST
            elif ing == "Queso en Barra 907g":
                unit_cost = ingredient_cost_map.get(ing)
                if unit_cost is None:
                    ok = False
                    audit.append((product_code, ing, "missing_input_cost"))
                    continue
                unit_cost = unit_cost / CHEESE_BAR_PORTIONS
            else:
                unit_cost = ingredient_cost_map.get(ing)
                if unit_cost is None:
                    ok = False
                    audit.append((product_code, ing, "missing_input_cost"))
                    continue

            total_cost += qty * unit_cost

        if ok:
            rows.append({
                "product_code": product_code,
                "unit_cost": round(total_cost, 2),
                "cost_source": "recipe",
                "active": 1
            })

    out = pd.DataFrame(rows).sort_values("product_code")
    out.to_csv(OUTPUT_FILE, index=False)

    # Auditoría simple
    if audit:
        audit_df = pd.DataFrame(audit, columns=["product_code", "ingredient_name", "issue"])
        audit_df.to_csv("data/processed_data/product_unit_cost_audit.csv", index=False)
        print(f"Audit written with {len(audit_df)} issues")

    print(f"Wrote product_unit_cost.csv ({len(out)} products)")

if __name__ == "__main__":
    main()
