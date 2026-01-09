import pandas as pd
from pathlib import Path

ANALYTICS_DIR = Path("data/analytics")
RAW_DIR = Path("data/raw_data")

PARQUET_FILES = [
    ANALYTICS_DIR / "ventas_2022.parquet",
    ANALYTICS_DIR / "ventas_2023.parquet",
    ANALYTICS_DIR / "ventas_2024.parquet",
    ANALYTICS_DIR / "ventas_2025.parquet",
]

COMANDAS_FILE = RAW_DIR / "comandas.xlsx"
OUTPUT_FILE = ANALYTICS_DIR / "fact_sales_raw.parquet"


def load_historical_parquets(files):
    frames = []
    for f in files:
        if not f.exists():
            raise FileNotFoundError(f"Missing parquet file: {f}")
        df = pd.read_parquet(f)
        df["fechaapertura"] = pd.to_datetime(df["fechaapertura"])
        frames.append(df)

    hist = pd.concat(frames, ignore_index=True)
    hist["sale_date"] = hist["fechaapertura"].dt.date
    return hist


def load_comandas(path):
    if not path.exists():
        print("No comandas.xlsx found. Skipping.")
        return None

    df = pd.read_excel(path)
    columnas_importantes = [
        "foliocuenta",
        "orden",
        "fechaapertura",
        "descripcion",
        "cantidad",
        "descuento",
        "importe",
    ]

    df = df[columnas_importantes].copy()
    df["fechaapertura"] = pd.to_datetime(df["fechaapertura"])
    df["sale_date"] = df["fechaapertura"].dt.date
    return df


def main():
    print("Loading historical parquet sales...")
    hist = load_historical_parquets(PARQUET_FILES)

    hist_dates = set(hist["sale_date"])
    print(
        f"Historical range: {min(hist_dates)} → {max(hist_dates)} "
        f"({len(hist_dates)} unique days)"
    )

    comandas = load_comandas(COMANDAS_FILE)

    if comandas is not None:
        last_hist_date = max(hist_dates)

        comandas_validas = comandas[comandas["sale_date"] > last_hist_date]

        if comandas_validas.empty:
            print(
                f"No new days found in comandas.xlsx "
                f"Last historical date: {last_hist_date}"
            )
            combined = hist
            all_dates = hist_dates
        
        else:
            print(
                f"Adding new sales from comandas.xlsx starting at "
                f"{comandas_validas['sale_date'].min()}"
            )    
            combined = pd.concat([hist, comandas_validas], ignore_index=True)
            all_dates=hist_dates | set(comandas_validas["sale_date"])
    else:
        combined = hist
        all_dates = hist_dates

    # Verificar huecos
    sorted_dates = sorted(all_dates)
    missing_days = []
    for i in range(1, len(sorted_dates)):
        if (sorted_dates[i] - sorted_dates[i - 1]).days > 1:
            missing_days.append((sorted_dates[i - 1], sorted_dates[i]))

    if missing_days:
        print("WARNING: Missing days detected:")
        for d1, d2 in missing_days[:5]:
            print(f"  Gap between {d1} and {d2}")

    print(f"Writing consolidated fact_sales_raw.parquet ({len(combined):,} rows)")
    combined.to_parquet(OUTPUT_FILE, index=False)
    print("Done.")


if __name__ == "__main__":
    main()
