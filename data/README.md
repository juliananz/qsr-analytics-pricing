# Raw Data Contract

This folder contains raw, immutable data exports.

## Sources

### 1. POS Sales Export
- Format: CSV
- One row per ordered item
- Extracted manually from POS system

### 2. Daily Cash Cuts
- Source: Google Form / Google Sheets
- One row per business day
- May include manual or form-based dates

## Rules
- Files are append-only
- No manual edits
- All normalization happens in ETL
