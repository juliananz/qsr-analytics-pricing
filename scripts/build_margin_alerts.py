import pandas as pd
from pathlib import Path

INPUT_FILE = Path("data/analytics/margin_summary.csv")
OUTPUT_FILE = Path("data/analytics/margin_alerts.csv")

# ============================
# CONFIGURACIÓN
# ============================
LOW_MARGIN_THRESHOLD = 0.30    # 30%
MIN_SALES_THRESHOLD = 5000.0   # MXN acumulados


def main():
    summary = pd.read_csv(INPUT_FILE)

    # Filtrar productos con volumen mínimo
    summary = summary[summary["total_sales"] >= MIN_SALES_THRESHOLD].copy()

    # Alertas de margen bajo
    low_margin = summary[
        summary["gross_margin_pct"] < LOW_MARGIN_THRESHOLD
    ].copy()

    if low_margin.empty:
        low_margin = pd.DataFrame(
            columns=[
                "product_code",
                "bundle_code",
                "total_sales",
                "gross_margin_pct",
                "alert_type"
            ]
        )
    else:
        low_margin["alert_type"] = "LOW_MARGIN"

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    low_margin.to_csv(OUTPUT_FILE, index=False)

    print(f"Wrote margin_alerts.csv ({len(low_margin)} alerts)")


if __name__ == "__main__":
    main()
