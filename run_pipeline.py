import subprocess
import sys

PIPELINE_STEPS = [
    ("Updating raw sales", "scripts/build_fact_sales_raw.py"),
    ("Building sales with margin", "scripts/build_fact_sales_margin.py"),
    ("Building margin summary", "scripts/build_margin_summary.py"),
    ("Building margin alerts", "scripts/build_margin_alerts.py"),
]

def run_step(description, script_path):
    print("\n" + "=" * 60)
    print(description)
    print("=" * 60)

    result = subprocess.run(
        [sys.executable, script_path],
        capture_output=True,
        text=True
    )

    print(result.stdout)

    if result.returncode != 0:
        print("ERROR:")
        print(result.stderr)
        raise RuntimeError(f"Pipeline failed at step: {description}")

def main():
    print("Starting QSR Analytics Pipeline")

    for description, script in PIPELINE_STEPS:
        run_step(description, script)

    print("\nPipeline completed successfully.")

if __name__ == "__main__":
    main()
