# Google Sheets Data Source

This document describes the expected structure for the Google Sheets used as
operational input for Cortes (daily cash closes) and Gastos (expenses).

## Spreadsheet Setup

1. Create a Google Spreadsheet with two sheets:
   - **Cortes** - Daily cash register close
   - **Gastos** - Operational expenses

2. Share the spreadsheet with the service account email as **Viewer**
   - Find the email in `.secrets/service_account.json` under `client_email`
   - Do NOT share with edit permissions

3. Copy the spreadsheet ID from the URL and set it in `config/sheets.yaml`
   - URL format: `https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit`

---

## Sheet: Cortes

Daily cash register close. One row per day.

### Required Columns

| Column (first line) | Description | Validation |
|---------------------|-------------|------------|
| Fecha | Close date | Valid date, unique per sheet |
| Ventas Efectivo | Cash sales (MXN) | Number >= 0 |
| Ventas Tarjeta | Card sales (MXN) | Number >= 0 |
| Ventas App | App/delivery sales (MXN) | Number >= 0 |
| Gastos Caja | Expenses from register (MXN) | Number >= 0 |
| Ventas Sistema | POS system total (MXN) | Number >= 0 |

### Header Format

Headers can include instructions and examples on additional lines:

```
Fecha

Escribe la fecha del cierre
Formato: DD/MM/AAAA
```

Only the first non-empty line ("Fecha") is used for matching.

### Example Data

| Fecha | Ventas Efectivo | Ventas Tarjeta | Ventas App | Gastos Caja | Ventas Sistema |
|-------|-----------------|----------------|------------|-------------|----------------|
| 15/01/2025 | 3500 | 2800 | 1200 | 450 | 7500 |
| 16/01/2025 | 4200 | 3100 | 980 | 320 | 8280 |

---

## Sheet: Gastos

Operational expenses. One row per expense.

### Required Columns

| Column (first line) | Description | Validation |
|---------------------|-------------|------------|
| Fecha | Expense date | Valid date |
| Descripcion | What was purchased | Non-empty |
| Categoria | Expense category | Non-empty (free text) |
| Monto | Amount in MXN | Number > 0 |

### Optional Columns

| Column (first line) | Description |
|---------------------|-------------|
| Proveedor | Supplier/vendor name |
| Elaboro | Who recorded the expense |

### Header Format

Headers can include instructions:

```
Categoria

Selecciona el tipo de gasto

Ejemplos: insumos, servicios, mantenimiento
```

Only "Categoria" is used for matching.

### Example Data

| Fecha | Descripcion | Proveedor | Categoria | Monto | Elaboro |
|-------|-------------|-----------|-----------|-------|---------|
| 15/01/2025 | Verduras semana | Fresh | insumos | 850 | Ana |
| 15/01/2025 | Gas LP | Zeta Gas | servicios | 1200 | |
| 16/01/2025 | Reparacion freidora | | mantenimiento | 450 | Pedro |

---

## Validation

### Cortes (Strict)
- All columns required
- Dates must be valid and unique (one close per day)
- All amounts must be >= 0

### Gastos (Structural Only)
- Required: fecha, descripcion, categoria, monto
- Optional: proveedor, elaboro
- Categoria is free text (no restricted values)
- Monto must be > 0

---

## Running Ingestion

```bash
python scripts/ingest_google_sheets.py
```

Outputs:
- `data/raw_data/cortes_validated.csv`
- `data/raw_data/gastos_validated.csv`

If validation fails, no files are written.

---

## Troubleshooting

| Error | Solution |
|-------|----------|
| "Access denied" | Share spreadsheet with service account email as Viewer |
| "Sheet not found" | Check sheet name matches config/sheets.yaml |
| "Unknown header" | Add header variant to config/sheets.yaml header_mapping |
| "Missing columns" | Add required column to Sheet |
| "Invalid date" | Check date format (DD/MM/YYYY recommended) |
