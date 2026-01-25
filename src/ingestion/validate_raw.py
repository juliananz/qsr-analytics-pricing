import pandas as pd
from pathlib import Path
import yaml
from src.utils.loaders import load_raw_file

RAW_DIR = Path("data/raw")
ANALYTICS_DIR = Path("data/analytics")
SCHEMA_PATH = Path("config/schema.yaml")


def load_schema():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_columns(df: pd.DataFrame, required_cols: list):
    missing = set(required_cols) - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def normalize_dates(series: pd.Series, formats: list):
    for fmt in formats:
        try:
            return pd.to_datetime(series, format=fmt)
        except Exception:
            continue
    raise ValueError("Date format not recognized")


def get_last_loaded_date():
    path = ANALYTICS_DIR / "fact_sales.parquet"
    if not path.exists():
        return None
    df = pd.read_parquet(path, columns=["sale_date"])
    return df["sale_date"].max()


def validate_sales_file(path: Path):
    schema = load_schema()
    df = pd.read_parquet(path)

    validate_columns(df, schema["pos_sales"]["required_columns"])

    df["fecha_norm"] = normalize_dates(
        df["fechaapertura"], schema["date_rules"]["accepted_formats"]
    )

    last_date = get_last_loaded_date()
    if last_date is not None:
        min_new_date = df["fecha_norm"].dt.date.min()
        if min_new_date <= last_date:
            raise ValueError(
                f"File contains already loaded dates. "
                f"Last loaded: {last_date}, new file starts at: {min_new_date}"
            )

    print(f"Validation OK for {path.name}")


if __name__ == "__main__":
    for file in RAW_DIR.glob("*.parquet"):
        validate_sales_file(file)
