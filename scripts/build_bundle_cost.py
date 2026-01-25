import pandas as pd
from pathlib import Path

BUNDLES_FILE = Path("data/processed_data/bundle_components.csv")
PRODUCT_COST_FILE = Path("data/processed_data/product_unit_cost.csv")
EXPECTED_SODA_FILE = Path("data/processed_data/expected_drink_cost.csv")
OUTPUT_FILE = Path("data/processed_data/bundle_unit_cost.csv")


def main():
    bundles = pd.read_csv(BUNDLES_FILE)
    prod_cost = pd.read_csv(PRODUCT_COST_FILE)
    soda_cost = pd.read_csv(EXPECTED_SODA_FILE)

    # Mapas de costo
    product_cost_map = prod_cost.set_index("product_code")["unit_cost"].to_dict()

    expected_soda_cost = float(
        soda_cost.loc[soda_cost["component_code"] == "drink_expected", "expected_unit_cost"].iloc[0]
    )

    rows = []

    for bundle_code, g in bundles.groupby("bundle_code"):
        total_cost = 0.0

        for _, r in g.iterrows():
            qty = r["quantity"]

            if r["component_type"] == "drink_expected":
                total_cost += expected_soda_cost * qty

            else:
                component = r["component_code"]
                if component not in product_cost_map:
                    raise ValueError(
                        f"Missing unit cost for component '{component}' "
                        f"in bundle '{bundle_code}'"
                    )
                total_cost += product_cost_map[component] * qty

        rows.append(
            {
                "bundle_code": bundle_code,
                "unit_cost": round(total_cost, 2),
                "cost_confidence": "low",  # por refresco + papas estimadas
            }
        )

    result = pd.DataFrame(rows).sort_values("bundle_code")
    result.to_csv(OUTPUT_FILE, index=False)
    print(f"Wrote bundle_unit_cost.csv ({len(result)} bundles)")


if __name__ == "__main__":
    main()
