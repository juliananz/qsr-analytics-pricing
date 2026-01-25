import pandas as pd
from pathlib import Path

SUMMARY_FILE = Path("data/analytics/margin_summary.csv")
SALES_FILE = Path("data/analytics/fact_sales_margin.parquet")
OUTPUT_FILE = Path("data/analytics/margin_alerts.csv")

# Umbrales (explícitos, fáciles de cambiar)
LOW_MARGIN_THRESHOLD = 0.40
HIGH_REVENUE_SHARE = 0.08
RECENT_DAYS = 30
MARGIN_DROP_THRESHOLD = 0.10


def main():
    summary = pd.read_csv(SUMMARY_FILE)
    sales = pd.read_parquet(SALES_FILE)

    alerts = []

    # --- Alerta 1: margen bajo ---
    low_margin = summary[summary["avg_margin_pct"] < LOW_MARGIN_THRESHOLD]
    for _, r in low_margin.iterrows():
        alerts.append({
            "item_code": r["item_code"],
            "alert_type": "low_avg_margin",
            "detail": f"Avg margin {r['avg_margin_pct']:.1%} below threshold",
            "severity": "medium"
        })

    # --- Alerta 2: alto revenue, bajo margen ---
    risky = summary[
        (summary["share_of_revenue"] > HIGH_REVENUE_SHARE) &
        (summary["avg_margin_pct"] < LOW_MARGIN_THRESHOLD)
    ]
    for _, r in risky.iterrows():
        alerts.append({
            "item_code": r["item_code"],
            "alert_type": "high_revenue_low_margin",
            "detail": f"Revenue share {r['share_of_revenue']:.1%}, margin {r['avg_margin_pct']:.1%}",
            "severity": "high"
        })

    # --- Alerta 3: deterioro reciente ---
    sales["item_code"] = sales["bundle_code"].fillna(sales["product_code"])
    sales["sale_date"] = pd.to_datetime(sales["sale_date"])

    cutoff = sales["sale_date"].max() - pd.Timedelta(days=RECENT_DAYS)

    recent = sales[sales["sale_date"] >= cutoff]
    hist = sales[sales["sale_date"] < cutoff]

    recent_margin = recent.groupby("item_code")["gross_margin_pct"].mean()
    hist_margin = hist.groupby("item_code")["gross_margin_pct"].mean()

    margin_change = (recent_margin - hist_margin).dropna()

    deteriorated = margin_change[margin_change < -MARGIN_DROP_THRESHOLD]
    for item, delta in deteriorated.items():
        alerts.append({
            "item_code": item,
            "alert_type": "margin_deterioration",
            "detail": f"Margin dropped {abs(delta):.1%} vs historical",
            "severity": "high"
        })

    alerts_df = pd.DataFrame(alerts)
    alerts_df.to_csv(OUTPUT_FILE, index=False)

    print(f"Wrote margin_alerts.csv ({len(alerts_df)} alerts)")


if __name__ == "__main__":
    main()
