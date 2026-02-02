"""
Ingest data from Google Sheets
==============================
Fetches Cortes and Gastos sheets, validates, and writes to CSV.

This script:
1. Authenticates via Google Service Account
2. Fetches sheet data via gspread
3. Normalizes headers (first line, lowercase, strip; accents preserved)
4. Maps known headers to canonical column names (ignores unmapped)
5. Validates data (Cortes: strict, Gastos: structural only)
6. Writes validated CSVs (fail-fast: no partial writes)

Usage:
    python scripts/ingest_google_sheets.py

Configuration:
    config/sheets.yaml - spreadsheet ID, credentials path, header mappings
"""

import sys
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml
import gspread
from google.oauth2.service_account import Credentials


# ============================================================
# CONFIGURATION
# ============================================================

CONFIG_DIR = Path("config")
SHEETS_CONFIG_PATH = CONFIG_DIR / "sheets.yaml"
SCHEMA_CONFIG_PATH = CONFIG_DIR / "schema.yaml"
OUTPUT_DIR = Path("data/raw_data")

# Need Drive scope to open by name, spreadsheets for reading
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly"
]


# ============================================================
# CONFIG LOADING
# ============================================================

def load_sheets_config() -> dict:
    """Load sheets.yaml configuration."""
    with open(SHEETS_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_schema_config() -> dict:
    """Load schema.yaml configuration."""
    with open(SCHEMA_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ============================================================
# AUTHENTICATION
# ============================================================

def get_client(credentials_path: str) -> gspread.Client:
    """
    Create authenticated gspread client.
    """
    creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    return gspread.authorize(creds)


# ============================================================
# HEADER NORMALIZATION
# ============================================================

def normalize_header(raw_header: str) -> str:
    """
    Normalize a raw header from Google Sheets.

    Steps:
    1. Split on line breaks
    2. Take first non-empty line
    3. Lowercase
    4. Strip whitespace

    Accents are PRESERVED.
    """
    if not raw_header:
        return ""

    lines = raw_header.split("\n")
    for line in lines:
        stripped = line.strip()
        if stripped:
            return stripped.lower()

    return ""


def map_headers(
    raw_headers: list[str],
    header_mapping: dict[str, str]
) -> dict[str, str]:
    """
    Map raw headers to canonical names.

    Returns dict: {raw_header: canonical_name} for mapped headers only.
    Unmapped headers are IGNORED (not included in result).
    """
    mapping_result = {}

    for raw in raw_headers:
        normalized = normalize_header(raw)
        if normalized in header_mapping:
            mapping_result[raw] = header_mapping[normalized]
        # Unmapped headers are silently ignored

    return mapping_result


# ============================================================
# DATA FETCHING
# ============================================================

def fetch_sheet_data(
    spreadsheet: gspread.Spreadsheet,
    sheet_name: str,
    header_mapping: dict[str, str]
) -> tuple[dict[str, str], list[dict]]:
    """
    Fetch data from a Google Sheet.

    Returns:
        (header_map, records) where:
        - header_map: {raw_header: canonical_name} for mapped columns only
        - records: list of dicts with canonical names as keys
    """
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        raise ValueError(f"Sheet '{sheet_name}' not found in spreadsheet.")

    all_values = worksheet.get_all_values()

    if len(all_values) < 1:
        raise ValueError(f"Sheet '{sheet_name}' has no headers.")

    raw_headers = all_values[0]

    if len(all_values) < 2:
        raise ValueError(f"Sheet '{sheet_name}' has no data rows.")

    # Map headers (only mapped ones)
    header_map = map_headers(raw_headers, header_mapping)

    if not header_map:
        raise ValueError(
            f"Sheet '{sheet_name}': No headers matched the mapping.\n"
            f"  Raw headers: {[normalize_header(h) for h in raw_headers]}\n"
            f"  Expected: {list(header_mapping.keys())}"
        )

    # Build records with canonical column names (only mapped columns)
    records = []
    for row_idx, row in enumerate(all_values[1:], start=2):
        # Skip completely empty rows
        if not any(cell.strip() for cell in row):
            continue

        record = {}
        for col_idx, raw_header in enumerate(raw_headers):
            if raw_header in header_map:
                canonical = header_map[raw_header]
                value = row[col_idx] if col_idx < len(row) else ""
                record[canonical] = value

        records.append(record)

    if not records:
        raise ValueError(f"Sheet '{sheet_name}' has no data rows (all empty).")

    return header_map, records


# ============================================================
# VALIDATION: CORTES (STRICT)
# ============================================================

def validate_cortes(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Validate Cortes data (strict validation).

    Rules:
    - Required columns: fecha, ventas_efectivo, ventas_tarjeta, ventas_app, gastos_caja, ventas_sistema
    - fecha must be valid date
    - Duplicate dates are removed (keeps last entry, logs warning)
    - All numeric columns must be >= 0

    Returns (cleaned_df, errors) where errors is list of validation errors.
    """
    errors = []
    required = ["fecha", "ventas_efectivo", "ventas_tarjeta", "ventas_app", "gastos_caja", "ventas_sistema"]

    # Check required columns
    missing = set(required) - set(df.columns)
    if missing:
        errors.append(f"Missing required columns: {sorted(missing)}")
        return df, errors  # Can't continue without required columns

    # Store original fecha for error messages
    original_fecha = df["fecha"].copy()

    # Validate fecha - handle both "01-10-25" and "25/10/2025 14:46:14" formats
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce", dayfirst=True)
    invalid_dates = df[df["fecha"].isna()].index.tolist()
    if invalid_dates:
        for idx in invalid_dates:
            errors.append(f"Row {idx + 2}: invalid date '{original_fecha.iloc[idx]}'")

    # Normalize to date only (strip time)
    df["fecha"] = df["fecha"].dt.normalize()

    # Remove duplicate dates (keep last entry)
    valid_dates = df[df["fecha"].notna()]
    duplicates = valid_dates[valid_dates["fecha"].duplicated(keep="last")]
    if not duplicates.empty:
        dup_dates = duplicates["fecha"].dt.strftime("%Y-%m-%d").unique()
        for d in dup_dates:
            print(f"  [WARN] Duplicate date {d} found, keeping last entry")
        # Remove duplicates, keep last
        df = df.drop(duplicates.index)

    # Validate numeric columns (non-negative)
    numeric_cols = ["ventas_efectivo", "ventas_tarjeta", "ventas_app", "gastos_caja", "ventas_sistema"]
    for col in numeric_cols:
        original_vals = df[col].copy()
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce")
        invalid = df[(df[col].isna()) | (df[col] < 0)]
        for idx in invalid.index:
            orig_val = original_vals.iloc[idx]
            if pd.isna(df.loc[idx, col]):
                errors.append(f"Row {idx + 2}: {col} is not a valid number ('{orig_val}')")
            else:
                errors.append(f"Row {idx + 2}: {col} must be >= 0, got {df.loc[idx, col]}")

    return df, errors


# ============================================================
# VALIDATION: GASTOS (STRUCTURAL ONLY)
# ============================================================

def validate_gastos(df: pd.DataFrame, schema: dict) -> tuple[pd.DataFrame, list[str]]:
    """
    Validate Gastos data (structural validation only).

    Rules:
    - Required columns from schema
    - fecha must be valid date (duplicates allowed)
    - descripcion must be non-empty
    - categoria must be non-empty (FREE TEXT, no enum)
    - monto must be numeric and > 0

    Returns (df, errors) where errors is list of validation errors.
    """
    errors = []
    required = schema.get("gastos", {}).get("required_columns", [])

    # Check required columns
    missing = set(required) - set(df.columns)
    if missing:
        errors.append(f"Missing required columns: {sorted(missing)}")
        return df, errors

    # Store original fecha for error messages
    original_fecha = df["fecha"].copy()

    # Validate fecha - handle both formats (duplicates allowed for Gastos)
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce", dayfirst=True)
    invalid_dates = df[df["fecha"].isna()].index.tolist()
    for idx in invalid_dates:
        errors.append(f"Row {idx + 2}: invalid date '{original_fecha.iloc[idx]}'")

    # Normalize to date only (strip time)
    df["fecha"] = df["fecha"].dt.normalize()

    # Validate descripcion non-empty
    empty_desc = df[df["descripcion"].astype(str).str.strip() == ""].index.tolist()
    for idx in empty_desc:
        errors.append(f"Row {idx + 2}: empty descripcion")

    # Validate categoria non-empty (FREE TEXT, no enum validation)
    empty_cat = df[df["categoria"].astype(str).str.strip() == ""].index.tolist()
    for idx in empty_cat:
        errors.append(f"Row {idx + 2}: empty categoria")

    # Validate monto > 0
    original_monto = df["monto"].copy()
    df["monto"] = pd.to_numeric(df["monto"].astype(str).str.replace(",", ""), errors="coerce")
    invalid_monto = df[df["monto"].isna() | (df["monto"] <= 0)]
    for idx in invalid_monto.index:
        orig_val = original_monto.iloc[idx]
        if pd.isna(df.loc[idx, "monto"]):
            errors.append(f"Row {idx + 2}: monto is not a valid number ('{orig_val}')")
        else:
            errors.append(f"Row {idx + 2}: monto must be > 0, got {df.loc[idx, 'monto']}")

    return df, errors


# ============================================================
# PROCESSING
# ============================================================

def process_sheet(
    spreadsheet: gspread.Spreadsheet,
    sheet_config: dict,
    sheet_key: str,
    schema: dict
) -> Optional[pd.DataFrame]:
    """
    Fetch, normalize, validate, and return DataFrame for a sheet.

    Returns DataFrame with canonical column names, or None if validation fails.
    """
    sheet_name = sheet_config["sheet_name"]
    header_mapping = sheet_config["header_mapping"]

    print(f"\nProcessing {sheet_name}...")

    # Fetch data
    header_map, records = fetch_sheet_data(spreadsheet, sheet_name, header_mapping)
    print(f"  Fetched {len(records)} rows")
    print(f"  Mapped columns: {list(header_map.values())}")

    # Build DataFrame
    df = pd.DataFrame(records)
    original_count = len(df)

    # Validate (and clean for Cortes)
    if sheet_key == "cortes":
        df, errors = validate_cortes(df)
    elif sheet_key == "gastos":
        df, errors = validate_gastos(df, schema)
    else:
        errors = []

    if errors:
        print(f"\n[ERROR] {sheet_name} validation failed:", file=sys.stderr)
        for err in errors[:20]:  # Limit error output
            print(f"  {err}", file=sys.stderr)
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more errors", file=sys.stderr)
        return None

    # Report if rows were removed
    if len(df) < original_count:
        print(f"  [INFO] Removed {original_count - len(df)} duplicate rows")

    print(f"  [OK] Validation passed ({len(df)} rows)")
    return df


# ============================================================
# MAIN
# ============================================================

def main():
    print("Google Sheets Ingestion")
    print("=" * 50)

    # Load config
    sheets_config = load_sheets_config()
    schema = load_schema_config()

    credentials_path = sheets_config.get("credentials_path")
    spreadsheet_name = sheets_config.get("spreadsheet_name")
    spreadsheet_id = sheets_config.get("spreadsheet_id")

    if not credentials_path:
        print("[ERROR] credentials_path not configured in config/sheets.yaml", file=sys.stderr)
        sys.exit(1)

    if not Path(credentials_path).exists():
        print(f"[ERROR] Credentials file not found: {credentials_path}", file=sys.stderr)
        sys.exit(1)

    # Authenticate
    print(f"\nAuthenticating with {Path(credentials_path).name}...")
    client = get_client(credentials_path)
    print("  [OK] Authenticated")

    # Open spreadsheet
    print(f"\nOpening spreadsheet...")
    try:
        if spreadsheet_id:
            spreadsheet = client.open_by_key(spreadsheet_id)
        elif spreadsheet_name:
            spreadsheet = client.open(spreadsheet_name)
        else:
            print("[ERROR] Neither spreadsheet_id nor spreadsheet_name configured", file=sys.stderr)
            sys.exit(1)
        print(f"  [OK] Opened: {spreadsheet.title}")
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"[ERROR] Spreadsheet not found", file=sys.stderr)
        sys.exit(1)
    except gspread.exceptions.APIError as e:
        print(f"[ERROR] API error: {e}", file=sys.stderr)
        sys.exit(1)

    # Process sheets
    results = {}
    all_valid = True

    for sheet_key, sheet_config in sheets_config["sheets"].items():
        try:
            df = process_sheet(spreadsheet, sheet_config, sheet_key, schema)
            if df is None:
                all_valid = False
            else:
                results[sheet_key] = df
        except Exception as e:
            print(f"\n[ERROR] {sheet_key}: {e}", file=sys.stderr)
            all_valid = False

    # Only write if all valid
    if not all_valid:
        print("\n" + "=" * 50)
        print("Ingestion FAILED. No files written.", file=sys.stderr)
        sys.exit(1)

    # Write outputs
    print("\n" + "=" * 50)
    print("Writing validated CSVs...")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for sheet_key, df in results.items():
        output_path = OUTPUT_DIR / f"{sheet_key}_validated.csv"
        df.to_csv(output_path, index=False)
        print(f"  Wrote {output_path} ({len(df)} rows)")

    print("\nIngestion completed successfully.")


if __name__ == "__main__":
    main()
