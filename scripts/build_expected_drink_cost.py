import pandas as pd
from pathlib import Path

DRINK_COST_FILE = Path("data/processed_data/dim_drink_cost.csv")
PURCHASE_DIST_FILE = Path("data/processed_data/drink_purchase_distribution.csv")
OUTPUT_FILE = Path("data/processed_data/expected_drink_cost.csv")

def main():
    costs = pd.read_csv(DRINK_COST_FILE)
    purchases = pd.read_csv(PURCHASE_DIST_FILE)

    df = purchases.merge(
        costs[["drink_code", "unit_cost", "drink_type"]],
        on="drink_code",
        how="left"
    )

    if df["unit_cost"].isna().any():
        missing = df[df["unit_cost"].isna()]["drink_code"].tolist()
        raise ValueError(f"Missing unit cost for: {missing}")

    df["weight"] = df["units_purchased"] / df["units_purchased"].sum()
    df["weighted_cost"] = df["unit_cost"] * df["weight"]

    expected_cost = df["weighted_cost"].sum()

    out = pd.DataFrame([{
        "component_code": "drink_expected",
        "expected_unit_cost": round(expected_cost, 2),
        "cost_confidence": "high",
        "method": "purchase_weighted_average"
    }])

    out.to_csv(OUTPUT_FILE, index=False)
    print(f"Expected drink cost: {round(expected_cost,2)}")

if __name__ == "__main__":
    main()
