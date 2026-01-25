import pandas as pd
from pathlib import Path

# =========================
# Paths
# =========================
HIST_FILE = Path("data/analytics/fact_sales.parquet")
RAW_FILE = Path("data/raw_data/comandas.xlsx")
OUTPUT_FILE = Path("data/analytics/fact_sales.parquet")

# =========================
# Columnas esperadas del POS
# =========================
COLS = [
    "foliocuenta",
    "orden",
    "fechaapertura",
    "descripcion",
    "cantidad",
    "descuento",
    "importe"
]

def main():
    # -------------------------------------------------
    # 1. Cargar histórico
    # -------------------------------------------------
    print("Loading historical sales...")
    if HIST_FILE.exists():
        hist = pd.read_parquet(HIST_FILE)

        # Asegurar tipo correcto
        hist["sale_date"] = pd.to_datetime(hist["sale_date"]).dt.normalize()

        existing_days = set(hist["sale_date"].dt.date.unique())

        print(
            f"Historical range: "
            f"{min(existing_days)} -> {max(existing_days)} "
            f"({len(existing_days)} days)"
        )
    else:
        hist = pd.DataFrame()
        existing_days = set()
        print("No historical file found. Starting fresh.")

    # -------------------------------------------------
    # 2. Cargar archivo nuevo del POS
    # -------------------------------------------------
    print("Loading new POS file...")
    raw = pd.read_excel(RAW_FILE)
    raw = raw[COLS].copy()

    # Normalizar fecha (Timestamp, no datetime.date)
    raw["sale_date"] = pd.to_datetime(raw["fechaapertura"]).dt.normalize()

    incoming_days = set(raw["sale_date"].dt.date.unique())

    # -------------------------------------------------
    # 3. Detectar días realmente nuevos
    # -------------------------------------------------
    new_days = sorted(incoming_days - existing_days)

    if not new_days:
        print("No new days detected. Nothing to add.")
        return

    print(
        f"New days detected: "
        f"{new_days[0]} -> {new_days[-1]} "
        f"({len(new_days)} days)"
    )

    # -------------------------------------------------
    # 4. Filtrar solo días nuevos
    # -------------------------------------------------
    raw_new = raw[raw["sale_date"].dt.date.isin(new_days)].copy()

    # -------------------------------------------------
    # 5. Normalizar columnas finales
    # -------------------------------------------------
    raw_new = raw_new.rename(columns={
        "descripcion": "product_name",
        "cantidad": "quantity",
        "importe": "net_amount"
    })

    raw_new["quantity"] = raw_new["quantity"].astype(float)
    raw_new["net_amount"] = raw_new["net_amount"].astype(float)

    # -------------------------------------------------
    # 6. Concatenar histórico + nuevo
    # -------------------------------------------------
    if hist.empty:
        combined = raw_new.copy()
    else:
        combined = pd.concat([hist, raw_new], ignore_index=True)

    # -------------------------------------------------
    # 7. Ordenar (ya no hay mezcla de tipos)
    # -------------------------------------------------
    combined = combined.sort_values(
        ["sale_date", "foliocuenta", "orden"]
    )

    # -------------------------------------------------
    # 8. Guardar
    # -------------------------------------------------
    combined.to_parquet(OUTPUT_FILE, index=False)

    print(
        f"Wrote fact_sales.parquet with "
        f"{combined['sale_date'].nunique()} unique days."
    )

# =========================
# Entry point
# =========================
if __name__ == "__main__":
    main()
