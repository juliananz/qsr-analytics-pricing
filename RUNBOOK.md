# RUNBOOK

## 1. How to run the pipeline locally

All commands must be run from the project root. All file paths in the scripts are relative.

Google Sheets ingestion runs separately from the POS pipeline. To pull the latest Cortes and Gastos data from the spreadsheet:

```
python scripts/ingest_google_sheets.py
```

This requires credentials. The script resolves them in this order: the `GOOGLE_CREDENTIALS_JSON` environment variable (a JSON string), then `GOOGLE_CREDENTIALS_PATH` (a path to a service account file), then `credentials_path` in `config/sheets.yaml`. Locally, `config/sheets.yaml` points to a Windows path at `D:\DS\Astro Burger\Negocio\astroburger-a7b14d51c891.json`. If that file isn't on your machine, use the env var instead. The script writes `data/raw_data/cortes_validated.csv` and `data/raw_data/gastos_validated.csv`. If validation fails for any sheet, nothing is written.

To run the main pipeline (incremental POS + margins + summary + alerts):

```
python run_pipeline.py
```

This assumes `data/analytics/fact_sales_raw.parquet` already exists and `data/raw_data/comandas.xlsx` contains new data beyond the last date in the parquet. If you need to rebuild the raw sales file from scratch using all historical POS files in `data/raw_data/POS/`:

```
python run_pipeline.py --rebuild-sales
```

The historical files are bimonthly exports named like `1_2_25.xlsx` (months 1-2 of 2025). They are gitignored and must be present locally for a full rebuild.


## 2. How to add a new product to cost mapping

When a product appears in the POS data but isn't recognized, it falls through to the fallback: cost is estimated at 55% of the sale price, and `cost_estimated` is set to true. The audit summary printed by `build_fact_sales_margin.py` shows the percentage of revenue covered by estimated costs. If that number is growing, new products need to be mapped.

Step one: find the exact name as it appears in the POS data. Look in `fact_sales_raw.parquet` under the `descripcion` column, or check the audit output for unmapped products.

Step two: add a row to `data/processed_data/product_name_mapping.csv`. The columns are `raw_product_name`, `product_code`, `mapping_confidence`, `notes`, `active`, and `bundle_code`. Set `active` to 1. If it's a combo, fill in `bundle_code` and leave `product_code` blank; the margin script will look up the bundle cost instead. If it's a standalone product, fill in `product_code` and leave `bundle_code` blank.

Step three: if the product is standalone and not yet in `data/processed_data/product_unit_cost.csv`, you have two options. If it has a known recipe, add the ingredient rows to `data/processed_data/recipe_items.csv` (columns: `product_code`, `ingredient_name`, `quantity`, `unit`, `notes`, `active`) and then regenerate the cost file:

```
python scripts/build_product_unit_cost_from_recipes.py
```

If it has no recipe but a known direct cost, add the row to `product_unit_cost.csv` directly with `cost_source` set to `direct_cost`.

Step four: re-run the margin script to apply the mapping:

```
python scripts/build_fact_sales_margin.py
```


## 3. How to update ingredient costs

Ingredient costs live in `data/processed_data/dim_input_costs.csv`. The columns are `ingredient_group`, `ingredient_name`, `package_price`, `package_units`, `unit_cost`, `cost_confidence`, and `active`.

`unit_cost` is not calculated by the script — it is stored explicitly in the CSV. When a supplier changes their price, update `package_price`, recalculate `unit_cost` manually as `package_price / package_units`, and save both values. `cost_confidence` should be `high` if the price came from an actual invoice and `low` if it's an estimate.

After editing `dim_input_costs.csv`, regenerate product costs from recipes:

```
python scripts/build_product_unit_cost_from_recipes.py
```

This reads `recipe_items.csv` and `dim_input_costs.csv` and overwrites `product_unit_cost.csv`. It will fail loudly if any ingredient referenced in a recipe is missing from `dim_input_costs.csv` or has `active` set to 0.

Then re-run the full margin pipeline to propagate the new costs through to `fact_sales_margin.parquet`:

```
python scripts/build_fact_sales_margin.py
python scripts/build_margin_summary.py
python scripts/build_margin_alerts.py
```


## 4. How to recover from a failed pipeline run

Each script writes its output only on success, so a mid-pipeline failure leaves the previous outputs intact. The safe recovery in most cases is to fix the underlying problem and re-run from the failing step.

If `ingest_google_sheets.py` fails: the validated CSVs are not written. The dashboard will continue showing data from the last successful run. Fix the credentials or the data issue in Google Sheets and re-run the script. Common causes: expired service account credentials, a duplicate date in the Cortes sheet, or a non-numeric value in a money column.

If `build_fact_sales_incremental.py` fails: `fact_sales_raw.parquet` is unchanged. The script only appends rows with dates newer than the last date already in the parquet. Re-run after fixing the issue with `comandas.xlsx`. If the file has no new dates beyond what's already loaded, the script exits cleanly with "No new days detected."

If `build_fact_sales_margin.py` fails: the previous `fact_sales_margin.parquet` remains. Common cause is a missing product mapping or a NaN in `unit_cost`. The audit output will identify the problem. Fix the mapping or cost file and re-run.

If the parquet files are corrupted or need to be rebuilt from scratch:

```
python run_pipeline.py --rebuild-sales
```

This reads all files in `data/raw_data/POS/` and rebuilds `fact_sales_raw.parquet` from zero before running the rest of the pipeline. You need the historical POS Excel files locally. They are gitignored.


## 5. How to check if the dashboard is showing stale data

The "Hoy" page shows the date of the most recent entry in `data/raw_data/cortes_validated.csv` as its reference date. If that date is not today, either today's corte hasn't been entered in Google Sheets yet, or the pipeline hasn't run since it was entered.

There is no automatic staleness banner in the dashboard. To check manually: look at the date caption under the "Hoy" title. If it shows yesterday or earlier, the data is stale.

To check from the command line, inspect the most recent sale date in the margin parquet:

```python
import pandas as pd
df = pd.read_parquet("data/analytics/fact_sales_margin.parquet", columns=["sale_date"])
print(df["sale_date"].max())
```

If the CI pipeline ran but the data is still old, check the GitHub Actions log for the most recent "Daily Pipeline" run. A successful run ends with a git commit message "chore: daily pipeline update". If the run succeeded but the cortes date is old, the corte for that day hasn't been submitted to Google Sheets yet.

TODO: add a stale data warning banner to the dashboard that triggers when the last corte is more than one day old.


## 6. How the CI pipeline works

The workflow is defined in `.github/workflows/daily-pipeline.yml`. It runs on three triggers: a daily cron at 13:00 UTC (7:00 AM Mexico City time), a push to `data/raw_data/comandas.xlsx`, and manual dispatch from the GitHub Actions UI.

When triggered, the workflow runs on `ubuntu-latest` with Python 3.11. It installs only the pipeline dependencies (pandas, pyarrow, openpyxl, pyyaml, gspread, google-auth). Streamlit and plotting libraries are not installed in CI.

The Google service account credentials are stored as a GitHub Actions secret named `GOOGLE_CREDENTIALS_JSON`. The workflow writes this to `/tmp/sa.json` at the start and deletes it at the end, even if the pipeline fails.

The steps run in this order: ingest Google Sheets, then incremental POS if `comandas.xlsx` exists (failures here are suppressed so the rest of the pipeline can continue), then build margins, then build summary and alerts.

After a successful run, the workflow commits and pushes the updated data files back to the repository. The commit is made by `github-actions[bot]`. The files committed are `data/raw_data/*_validated.csv`, everything under `data/analytics/`, and `data/processed_data/margin_alerts.csv`. This is what makes the updated data available to the Streamlit Cloud deployment without manual intervention.

The POS upload in the dashboard sidebar commits `data/raw_data/comandas.xlsx` directly to the repository via the GitHub API using a token stored in Streamlit secrets. This push matches the workflow's path filter and triggers the pipeline automatically, usually within two minutes.
