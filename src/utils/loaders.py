import pandas as pd
from pathlib import Path


def load_raw_file(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)

    if path.suffix == ".xls":
        return pd.read_excel(path, engine="xlrd")

    if path.suffix == ".xlsx":
        return pd.read_excel(path)

    raise ValueError(f"Unsupported file type: {path.suffix}")
