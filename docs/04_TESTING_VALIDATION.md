# Testing and Validation Strategy

## Overview

This document outlines the testing and validation approach for the QSR Analytics & Pricing System. The strategy emphasizes data quality validation, contract testing, and business rule verification.

---

## Validation Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                     VALIDATION PYRAMID                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│                        ┌───────────┐                            │
│                        │ Business  │  ← Manual Review           │
│                        │   Rules   │    (Margin Reasonableness) │
│                        └─────┬─────┘                            │
│                              │                                   │
│                    ┌─────────┴─────────┐                        │
│                    │   Data Quality    │  ← Automated Checks    │
│                    │   (Completeness,  │    (Audit Summary)     │
│                    │    Consistency)   │                        │
│                    └─────────┬─────────┘                        │
│                              │                                   │
│              ┌───────────────┴───────────────┐                  │
│              │      Schema Validation        │  ← Fail-Fast     │
│              │   (Types, Required Fields)    │    (At Ingestion)│
│              └───────────────┬───────────────┘                  │
│                              │                                   │
│        ┌─────────────────────┴─────────────────────┐            │
│        │           Source Data Integrity           │  ← External│
│        │      (POS Exports, Google Sheets)         │    Systems │
│        └───────────────────────────────────────────┘            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Schema Validation

### POS Data Schema (`config/schema.yaml`)

```yaml
pos_sales:
  required_columns:
    - foliocuenta
    - orden
    - fechaapertura
    - horacerrar
    - descripcion
    - cantidad
    - precio
    - descuento
    - importe
    - metodopago
    - vendedor
  types:
    foliocuenta: int64
    orden: int64
    fechaapertura: datetime64
    cantidad: float64
    precio: float64
    descuento: float64
    importe: float64
```

### Google Sheets Schema

**Cortes (Daily Cash Closes)**:
```yaml
cortes:
  required_columns:
    - fecha
    - ventas_efectivo
    - ventas_tarjeta
    - ventas_app
    - gastos_caja
    - ventas_sistema
  validation_rules:
    - unique: [fecha]
    - non_negative: [ventas_efectivo, ventas_tarjeta, ventas_app, gastos_caja]
```

**Gastos (Expenses)**:
```yaml
gastos:
  required_columns:
    - fecha
    - descripcion
    - categoria
    - monto
  optional_columns:
    - proveedor
    - elaboro
  validation_rules:
    - not_empty: [fecha, descripcion, categoria]
    - positive: [monto]
```

### Implementation

```python
# In build_fact_sales_raw_from_pos.py
REQUIRED_COLUMNS = [
    'foliocuenta', 'orden', 'fechaapertura', 'horacerrar',
    'descripcion', 'cantidad', 'precio', 'descuento',
    'importe', 'metodopago', 'vendedor'
]

def validate_schema(df, filename):
    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"{filename}: Missing columns: {missing}")
```

---

## 2. Data Quality Checks

### 2.1 Completeness Checks

| Check | Location | Action |
|-------|----------|--------|
| No null dates | `build_fact_sales_raw_from_pos.py` | Fail if null fechaapertura |
| No null amounts | `build_fact_sales_margin.py` | Fail if null importe |
| Product mapping coverage | Audit summary | Warn if >20% unmapped |
| Cost coverage | Audit summary | Report estimated vs. known |

### 2.2 Consistency Checks

| Check | Expected | Action |
|-------|----------|--------|
| importe = cantidad × precio - descuento | ±0.01 tolerance | Log warning |
| Dates within expected range | 2022-01-01 to today | Fail if outside |
| No future dates | sale_date ≤ today | Fail if future |
| Quantity > 0 | Positive values | Warn on negatives |

### 2.3 Uniqueness Checks

| Check | Level | Action |
|-------|-------|--------|
| Cortes date uniqueness | Per fecha | Keep last, log warning |
| No duplicate transactions | foliocuenta + orden | Not enforced (POS may have) |

---

## 3. Business Rule Validation

### 3.1 Margin Reasonableness

**Rule**: All products should have positive margins (except non-product revenue)

```python
def validate_margins(df):
    negative_margin = df[
        (df['gross_margin'] < 0) &
        (~df['non_product_revenue'])
    ]
    if len(negative_margin) > 0:
        print(f"WARNING: {len(negative_margin)} rows with negative margin")
        print(negative_margin.groupby('product_code')['gross_margin'].sum())
```

**Rule**: Margins should not exceed 90%

```python
def check_extreme_margins(df):
    extreme = df[df['gross_margin_pct'] > 0.90]
    if len(extreme) > 0:
        print(f"WARNING: {len(extreme)} rows with >90% margin - verify costs")
```

### 3.2 Cost Validation

**Rule**: unit_cost must NEVER be NaN

```python
# In build_fact_sales_margin.py - Critical invariant
assert df['unit_cost'].notna().all(), "CRITICAL: NaN found in unit_cost"
```

**Rule**: Costs should be within reasonable bounds

```python
def validate_cost_bounds(df):
    # No cost should exceed sale price (unless error)
    overcost = df[df['unit_cost'] > df['precio'] * 1.5]
    if len(overcost) > 0:
        print(f"WARNING: {len(overcost)} items with cost > 150% of price")
```

### 3.3 Revenue Reconciliation

**Rule**: Total system revenue should approximately match POS totals

```python
def reconcile_revenue(fact_sales, cortes):
    """Compare calculated revenue to reported daily totals"""
    calculated = fact_sales.groupby('sale_date')['net_amount'].sum()
    reported = cortes.set_index('fecha')['ventas_sistema']

    diff = (calculated - reported).abs() / reported
    mismatches = diff[diff > 0.05]  # >5% variance

    if len(mismatches) > 0:
        print(f"WARNING: Revenue variance >5% on {len(mismatches)} days")
```

---

## 4. Audit Summary

The `build_fact_sales_margin.py` script produces an audit summary after each run:

```
=== MARGIN ETL AUDIT SUMMARY ===

DATA VOLUME
  Total rows: 2,345,678
  Date range: 2022-01-01 to 2025-01-15
  Unique days: 1,095
  Unique products: 156

COST RESOLUTION
  Known costs: 2,100,000 (89.5%)
  Estimated costs: 245,678 (10.5%)

  By resolution level:
    Bundle lookup: 450,000 (19.2%)
    Product lookup: 1,200,000 (51.1%)
    Drink expected: 400,000 (17.0%)
    Fixed (avocado): 50,000 (2.1%)
    Fallback estimate: 245,678 (10.5%)

MARGIN STATISTICS
  Total revenue: $45,678,900.00 MXN
  Total cost: $25,123,456.00 MXN
  Gross margin: $20,555,444.00 MXN
  Average margin %: 45.0%

WARNINGS
  Products with negative margin: 5
    - product_x: -$1,234.00
    - product_y: -$567.00
  Products with >90% margin: 2
    - adjustment_1: 100%
    - special_item: 95%

NON-PRODUCT REVENUE
  Total non-product: $234,567.00
  Categories: ENVIO, AJUSTE, EXCEDENTE

================================
```

---

## 5. Test Cases

### 5.1 Unit Tests (Recommended Implementation)

```python
# tests/test_cost_resolution.py

def test_bundle_cost_lookup():
    """Bundle products should use bundle_unit_cost"""
    row = {'bundle_code': 'bundle_1', 'product_code': None}
    cost = resolve_cost(row, bundle_costs={'bundle_1': 45.0})
    assert cost == 45.0

def test_product_cost_lookup():
    """Mapped products should use product_unit_cost"""
    row = {'bundle_code': None, 'product_code': 'burger_cheese'}
    cost = resolve_cost(row, product_costs={'burger_cheese': 27.75})
    assert cost == 27.75

def test_fallback_estimation():
    """Unmapped products should use 55% fallback"""
    row = {'bundle_code': None, 'product_code': None, 'precio': 100.0}
    cost, estimated = resolve_cost(row)
    assert cost == 55.0
    assert estimated == True

def test_non_product_revenue():
    """Non-product items should have cost = price"""
    row = {'product_name': 'ENVIO UBER', 'precio': 25.0}
    cost = resolve_cost(row)
    assert cost == 25.0  # 0% margin

def test_unit_cost_never_nan():
    """Critical: unit_cost must never be NaN"""
    df = build_fact_sales_margin()
    assert df['unit_cost'].notna().all()
```

### 5.2 Integration Tests (Recommended Implementation)

```python
# tests/test_pipeline_integration.py

def test_full_pipeline_produces_outputs():
    """Pipeline should produce all expected output files"""
    run_pipeline()

    assert Path('data/analytics/fact_sales_raw.parquet').exists()
    assert Path('data/analytics/fact_sales_margin.parquet').exists()
    assert Path('data/analytics/margin_summary.csv').exists()
    assert Path('data/analytics/margin_alerts.csv').exists()

def test_incremental_is_idempotent():
    """Running incremental twice should not duplicate data"""
    run_incremental()
    count1 = len(pd.read_parquet('data/analytics/fact_sales_raw.parquet'))

    run_incremental()
    count2 = len(pd.read_parquet('data/analytics/fact_sales_raw.parquet'))

    assert count1 == count2

def test_margin_calculation_consistency():
    """Margin should equal revenue - cost"""
    df = pd.read_parquet('data/analytics/fact_sales_margin.parquet')

    calculated = df['net_amount'] - df['total_cost']
    assert np.allclose(df['gross_margin'], calculated, atol=0.01)
```

### 5.3 Data Quality Tests (Recommended Implementation)

```python
# tests/test_data_quality.py

def test_no_future_dates():
    """Sales dates should not be in the future"""
    df = pd.read_parquet('data/analytics/fact_sales_raw.parquet')
    assert df['sale_date'].max() <= pd.Timestamp.today()

def test_positive_quantities():
    """Quantities should generally be positive"""
    df = pd.read_parquet('data/analytics/fact_sales_margin.parquet')
    negative_pct = (df['quantity'] < 0).mean()
    assert negative_pct < 0.01  # <1% negative allowed (refunds)

def test_cost_coverage():
    """At least 80% of revenue should have known costs"""
    df = pd.read_parquet('data/analytics/fact_sales_margin.parquet')
    known_pct = (~df['cost_estimated']).mean()
    assert known_pct >= 0.80
```

---

## 6. Validation Checklist

### Daily Operations Checklist

- [ ] Pipeline completed without errors
- [ ] Audit summary reviewed
- [ ] No new products in fallback estimation
- [ ] No unexpected negative margins
- [ ] Row count increased as expected
- [ ] Date range extended to today

### Weekly Review Checklist

- [ ] Cost coverage >85%
- [ ] Margin alerts reviewed and actioned
- [ ] Revenue reconciliation with cortes
- [ ] New product mappings added if needed
- [ ] Cost sensitivity scenarios reviewed

### Monthly Review Checklist

- [ ] Ingredient costs updated
- [ ] Recipe accuracy verified
- [ ] Bundle compositions confirmed
- [ ] Drink purchase distribution updated
- [ ] Historical trends analyzed

---

## 7. Error Recovery

### Schema Validation Failure

```
ERROR: Missing columns: {'metodopago'}
```

**Recovery**:
1. Check POS export settings
2. Verify column names match expected (case-sensitive)
3. Add column to source file or update schema

### Google Sheets Validation Failure

```
ERROR: Duplicate fecha found: 2025-01-15 (rows 45, 67)
```

**Recovery**:
1. Open Google Sheets
2. Remove duplicate entry (keep correct one)
3. Re-run ingestion

### Cost Resolution Warning

```
WARNING: 500 products using fallback estimation
  - "COMBO ESPECIAL": 234 transactions
  - "NUEVO PRODUCTO": 156 transactions
```

**Recovery**:
1. Add product to `product_name_mapping.csv`
2. Add recipe to `recipe_items.csv` if applicable
3. Re-run margin calculation

### Negative Margin Alert

```
WARNING: Products with negative margin:
  - burger_doble: -$5,678.00 (1,234 units)
```

**Recovery**:
1. Verify unit cost in `product_unit_cost.csv`
2. Check recipe in `recipe_items.csv`
3. Verify ingredient costs in `dim_input_costs.csv`
4. Consider price adjustment if cost is correct

---

## 8. Monitoring Metrics

### Key Performance Indicators

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Cost coverage | >85% | <80% |
| Average margin | 40-50% | <35% or >55% |
| Pipeline success rate | 100% | Any failure |
| Data freshness | Same day | >1 day lag |
| Fallback estimation | <15% | >20% |

### Dashboard Health Checks

```python
# Suggested monitoring script
def check_data_health():
    df = pd.read_parquet('data/analytics/fact_sales_margin.parquet')

    checks = {
        'last_date': df['sale_date'].max(),
        'days_stale': (pd.Timestamp.today() - df['sale_date'].max()).days,
        'total_rows': len(df),
        'cost_coverage': (~df['cost_estimated']).mean(),
        'avg_margin': df['gross_margin_pct'].mean(),
        'negative_margin_count': (df['gross_margin'] < 0).sum(),
    }

    # Alert conditions
    if checks['days_stale'] > 1:
        alert("Data is stale - last update: " + str(checks['last_date']))
    if checks['cost_coverage'] < 0.80:
        alert(f"Cost coverage low: {checks['cost_coverage']:.1%}")
    if checks['avg_margin'] < 0.35:
        alert(f"Average margin below target: {checks['avg_margin']:.1%}")

    return checks
```
