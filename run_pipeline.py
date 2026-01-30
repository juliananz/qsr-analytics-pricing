import subprocess
import argparse
import sys

PIPELINE_STEPS = [
    ("Building sales with margin", "scripts/build_fact_sales_margin.py"),
    ("Building margin summary", "scripts/build_margin_summary.py"),
    ("Building margin alerts", "scripts/build_margin_alerts.py"),
]

def run_step(description, script):
    print("\n" + "=" * 60)
    print(description)
    print("=" * 60)

    result = subprocess.run(
        [sys.executable, script],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print("\nERROR:")
        print(result.stderr)
        raise RuntimeError(f"Pipeline failed at step: {description}")

    print(result.stdout.strip())


def main():
    parser = argparse.ArgumentParser(description="QSR Analytics Pipeline")
    parser.add_argument(
        "--rebuild-sales",
        action="store_true",
        help="Rebuild fact_sales_raw from POS Excel files"
    )
    args = parser.parse_args()

    print("\nStarting QSR Analytics Pipeline")

    # -------------------------------
    # INGESTIÓN DE VENTAS
    # -------------------------------
    if args.rebuild_sales:
        run_step(
            "Rebuilding raw sales from POS historical Excel files",
            "scripts/build_fact_sales_raw_from_pos.py"
        )
    else:
        run_step(
            "Updating raw sales incrementally",
            "scripts/build_fact_sales_incremental.py"
        )

    # -------------------------------
    # ETL ANALÍTICO
    # -------------------------------
    for description, script in PIPELINE_STEPS:
        run_step(description, script)

    print("\nPipeline completed successfully.")


if __name__ == "__main__":
    main()
