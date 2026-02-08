# Complete Data Pipeline Documentation

## Pipeline Overview

The QSR Analytics data pipeline transforms raw POS exports and manual inputs into margin-enriched analytics ready for business consumption.

```
Raw POS Data → Normalized Transactions → Cost-Enriched Facts → Aggregated Summaries → Dashboard
```

---

## Pipeline Execution

### Full Pipeline Run

```bash
python run_pipeline.py
```

Executes: Incremental sales ingestion → Margin calculation → Summary aggregation → Alert generation

### Full Historical Rebuild

```bash
python run_pipeline.py --rebuild-sales
```

Executes: Full POS rebuild → Margin calculation → Summary aggregation → Alert generation

### Individual Script Execution

```bash
# Ingestion
python scripts/build_fact_sales_raw_from_pos.py      # Full historical rebuild
python scripts/build_fact_sales_incremental.py       # Daily append
python scripts/ingest_google_sheets.py               # Fetch Cortes & Gastos

# Cost Preparation
python scripts/build_product_unit_cost.py            # Recipe → product costs
python scripts/build_bundle_cost.py                  # Components → bundle costs
python scripts/build_expected_drink_cost.py          # Distribution → expected drink cost

# Analytics
python scripts/build_fact_sales_margin.py            # Main margin ETL
python scripts/build_margin_summary.py               # Product/bundle aggregates
python scripts/build_margin_alerts.py                # Low-margin alerts
python scripts/build_cost_sensitivity.py             # Scenario analysis
```

---

## Stage 1: Data Ingestion

### 1.1 POS Historical Ingestion

**Script**: `scripts/build_fact_sales_raw_from_pos.py`

**Purpose**: Load all historical POS exports and create normalized transaction fact table.

**Input**:
- `data/raw_data/POS/*.xlsx` - Historical POS exports (one file per period)

**Processing**:
1. Scan all Excel files in POS directory
2. Validate schema (11 required columns)
3. Normalize column names (lowercase, strip whitespace)
4. Parse dates with flexible format handling
5. Cast numeric types with error coercion
6. Add derived columns: `sale_datetime`, `sale_date`, `year`
7. Concatenate all files
8. Sort by sale_datetime

**Output**:
- `data/analytics/fact_sales_raw.parquet`

**Schema Contract**:
```
foliocuenta      : int64
orden            : int64
fechaapertura    : datetime64[ns]
horacerrar       : object (time string)
descripcion      : object (product name)
cantidad         : float64
precio           : float64
descuento        : float64
importe          : float64
metodopago       : object
vendedor         : object
sale_datetime    : datetime64[ns]
sale_date        : datetime64[ns]
year             : int64
```

**Validation Rules**:
- All 11 base columns must exist
- Date parsing must succeed (flexible format)
- Numeric columns must be coercible to float
- File must not be empty

### 1.2 Incremental Sales Ingestion

**Script**: `scripts/build_fact_sales_incremental.py`

**Purpose**: Append new daily sales without reprocessing history.

**Input**:
- `data/raw_data/comandas.xlsx` - Daily POS export
- `data/analytics/fact_sales_raw.parquet` - Existing fact table

**Processing**:
1. Load new Excel file
2. Apply same normalization as historical
3. Determine max date in existing fact table
4. Filter new data for dates > max existing date
5. Append new rows to parquet file

**Output**:
- `data/analytics/fact_sales_raw.parquet` (updated)

**Deduplication Strategy**:
- Date-based: Only dates not in existing data are appended
- Idempotent: Running twice on same file has no effect

### 1.3 Google Sheets Ingestion

**Script**: `scripts/ingest_google_sheets.py`

**Purpose**: Fetch and validate daily cash closes and expenses.

**Configuration** (`config/sheets.yaml`):
```yaml
spreadsheet_id: "1pLHT1VzW9yCtC_H0s17E7top3yeaY15u5BOsFpgkQlA"
credentials_path: "path/to/credentials.json"
sheets:
  cortes:
    sheet_name: "Cortes"
    header_mapping:
      "marca temporal": "fecha"
      "efectivo": "ventas_efectivo"
      "tarjeta": "ventas_tarjeta"
      "app": "ventas_app"
      "gastos de caja": "gastos_caja"
      "total de sistema": "ventas_sistema"
  gastos:
    sheet_name: "Gastos"
    header_mapping:
      "marca temporal": "fecha"
      "descripción": "descripcion"
      "categoría": "categoria"
      "monto": "monto"
```

**Processing (Cortes)**:
1. Authenticate via service account
2. Fetch all rows from Cortes sheet
3. Normalize headers (first line, lowercase)
4. Map headers via configuration
5. Validate: unique dates, non-negative numerics
6. Write validated data

**Processing (Gastos)**:
1. Same authentication and fetch
2. Header normalization and mapping
3. Validate: required fields non-empty, monto > 0

**Output**:
- `data/raw_data/cortes_validated.csv`
- `data/raw_data/gastos_validated.csv`

**Error Handling**: Fail-fast with detailed error messages

---

## Stage 2: Cost Preparation

### 2.1 Product Unit Cost Calculation

**Script**: `scripts/build_product_unit_cost.py`

**Input**:
- `data/processed_data/recipe_items.csv` - Product recipes
- `data/processed_data/dim_input_costs.csv` - Ingredient costs

**Processing**:
```
For each product:
  unit_cost = Σ(ingredient_cost × quantity)
```

**Output**: `data/processed_data/product_unit_cost.csv`

**Example**:
```
burger_cheese:
  pan_burger × 1 = 7.59
  carne_burger × 1 = 16.80
  queso_amarillo × 1 = 3.36
  Total = 27.75 MXN
```

### 2.2 Bundle Unit Cost Calculation

**Script**: `scripts/build_bundle_cost.py`

**Input**:
- `data/processed_data/bundle_components.csv`
- `data/processed_data/product_unit_cost.csv`
- `data/processed_data/expected_drink_cost.csv`

**Processing**:
```
For each bundle:
  unit_cost = Σ(component_cost × quantity)
  (drinks use expected_drink_cost)
```

**Output**: `data/processed_data/bundle_unit_cost.csv`

### 2.3 Expected Drink Cost

**Script**: `scripts/build_expected_drink_cost.py`

**Processing**:
```
expected_cost = Σ(drink_cost × units_purchased) / Σ(units_purchased)
```

**Output**: `data/processed_data/expected_drink_cost.csv`

---

## Stage 3: Margin Calculation (Core ETL)

**Script**: `scripts/build_fact_sales_margin.py`

### Cost Resolution Waterfall

```
1. Non-product revenue (ENVIO, AJUSTE, $) → cost = price
2. Bundle products → bundle_unit_cost lookup
3. Beverages → expected_drink_cost
4. Extra avocado → fixed 5.00 MXN
5. Mapped products → product_unit_cost lookup
6. Fallback → price × 0.55 (assumes 45% margin)
```

### Financial Calculations

```python
total_cost       = unit_cost × quantity
gross_margin     = net_amount - total_cost
gross_margin_pct = gross_margin / net_amount
```

### Output Schema

```
sale_date           : datetime64[ns]
product_name        : object
product_code        : object (nullable)
bundle_code         : object (nullable)
quantity            : float64
net_amount          : float64
unit_cost           : float64 (NEVER NaN)
total_cost          : float64
gross_margin        : float64
gross_margin_pct    : float64
cost_estimated      : bool
non_product_revenue : bool
```

**Output**: `data/analytics/fact_sales_margin.parquet`

---

## Stage 4: Aggregation

### 4.1 Margin Summary

**Script**: `scripts/build_margin_summary.py`

```python
summary = df.groupby(['product_code', 'bundle_code']).agg({
    'net_amount': 'sum',
    'quantity': 'sum',
    'total_cost': 'sum',
    'gross_margin': 'sum',
})
summary['gross_margin_pct'] = summary['gross_margin'] / summary['net_amount']
```

**Output**: `data/analytics/margin_summary.csv`

### 4.2 Margin Alerts

**Script**: `scripts/build_margin_alerts.py`

**Alert Criteria**:
- `gross_margin_pct < 30%`
- `total_sales >= 5000 MXN`

**Output**: `data/analytics/margin_alerts.csv`

### 4.3 Cost Sensitivity

**Script**: `scripts/build_cost_sensitivity.py`

**Scenarios**: +5%, +10% cost increases per ingredient

**Output**: `data/analytics/cost_sensitivity.csv`

---

## Data Lineage

```
POS Excel Files ──────────────────┐
                                  ▼
                         fact_sales_raw.parquet
                                  │
dim_input_costs ─► product_unit_cost ─┐
recipe_items ────┘                    │
                                      │
dim_drink_cost ─► expected_drink_cost─┤
drink_distribution ┘                  │
                                      │
bundle_components ─► bundle_unit_cost─┤
                                      │
product_name_mapping ─────────────────┤
                                      ▼
                         fact_sales_margin.parquet
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
           margin_summary.csv   cost_sensitivity   Dashboard
                    │                 .csv
                    ▼
           margin_alerts.csv
```

---

## Performance

| Stage | Duration | Output Size |
|-------|----------|-------------|
| Historical Ingestion | ~30 sec | 8 MB |
| Incremental Ingestion | ~2 sec | +few KB |
| Sheets Ingestion | ~5 sec | ~70 KB |
| Margin Calculation | ~15 sec | 2.3 MB |
| Aggregations | ~3 sec | ~10 KB |

**Total Pipeline**: ~1 minute (full), ~30 seconds (incremental)
