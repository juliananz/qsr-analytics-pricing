# System Architecture

## Overview

The QSR Analytics & Pricing System is a data pipeline and analytics platform for **Astro Burger**, a Mexican quick-service restaurant. The system processes point-of-sale (POS) data, calculates product margins, and provides actionable insights through a mobile-first dashboard.

## Architecture Diagram

```
                                    QSR Analytics & Pricing System
                                    ==============================

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                   DATA SOURCES                                       │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────────┐    │
│   │  POS System     │    │  Daily Excel    │    │     Google Sheets           │    │
│   │  (Historical)   │    │  Upload         │    │  ┌─────────┬───────────┐    │    │
│   │                 │    │                 │    │  │ Cortes  │  Gastos   │    │    │
│   │  data/raw_data/ │    │  comandas.xlsx  │    │  │ (Daily  │ (Expense  │    │    │
│   │  POS/*.xlsx     │    │                 │    │  │  Cuts)  │   Log)    │    │    │
│   └────────┬────────┘    └────────┬────────┘    │  └────┬────┴─────┬─────┘    │    │
│            │                      │              └───────┼──────────┼──────────┘    │
│            │                      │                      │          │               │
└────────────┼──────────────────────┼──────────────────────┼──────────┼───────────────┘
             │                      │                      │          │
             ▼                      ▼                      ▼          ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                               INGESTION LAYER                                        │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│   ┌─────────────────────────┐    ┌─────────────────────────────────────────────┐   │
│   │ build_fact_sales_raw_   │    │         ingest_google_sheets.py             │   │
│   │ from_pos.py             │    │                                             │   │
│   │ (Full Historical Build) │    │  • Google Service Account Auth              │   │
│   └────────────┬────────────┘    │  • Schema Validation (per config/sheets.yaml)│   │
│                │                 │  • Header Normalization                      │   │
│                │                 │  • Fail-fast on Validation Errors           │   │
│   ┌────────────┴────────────┐    └──────────────────────┬──────────────────────┘   │
│   │ build_fact_sales_       │                           │                          │
│   │ incremental.py          │                           │                          │
│   │ (Daily Append)          │                           │                          │
│   └────────────┬────────────┘                           │                          │
│                │                                        │                          │
└────────────────┼────────────────────────────────────────┼──────────────────────────┘
                 │                                        │
                 ▼                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                               STORAGE LAYER                                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│   ┌─────────────────────────────────────┐    ┌─────────────────────────────────┐   │
│   │        fact_sales_raw.parquet       │    │       Reference Data (CSV)      │   │
│   │        ~~~~~~~~~~~~~~~~~~~~~~~~     │    │                                 │   │
│   │  • 7.9M rows normalized POS data    │    │  • dim_input_costs.csv          │   │
│   │  • Immutable append-only            │    │  • recipe_items.csv             │   │
│   │  • Columnar format for fast reads   │    │  • bundle_components.csv        │   │
│   │  • ~8MB compressed                  │    │  • product_name_mapping.csv     │   │
│   └─────────────────┬───────────────────┘    │  • dim_drink_cost.csv           │   │
│                     │                        │  • drink_purchase_distribution  │   │
│                     │                        └─────────────────┬───────────────┘   │
│                     │                                          │                    │
│   ┌─────────────────┴──────────────────────────────────────────┴───────────────┐   │
│   │                    cortes_validated.csv │ gastos_validated.csv              │   │
│   └────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                               ANALYTICS LAYER (ETL)                                  │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│   ┌─────────────────────────────────────────────────────────────────────────────┐   │
│   │                      build_fact_sales_margin.py                              │   │
│   │                      ~~~~~~~~~~~~~~~~~~~~~~~~~~                              │   │
│   │                                                                              │   │
│   │    ┌─────────────────────────────────────────────────────────────────┐      │   │
│   │    │              COST RESOLUTION WATERFALL                          │      │   │
│   │    │  ┌─────────────────────────────────────────────────────────┐   │      │   │
│   │    │  │ 1. Non-product revenue (ENVIO, AJUSTE) → cost = price   │   │      │   │
│   │    │  │ 2. Bundle products → bundle_unit_cost.csv               │   │      │   │
│   │    │  │ 3. Beverages → expected_drink_cost.csv                  │   │      │   │
│   │    │  │ 4. Extra avocado → fixed 5.00 MXN                       │   │      │   │
│   │    │  │ 5. Mapped products → product_unit_cost.csv              │   │      │   │
│   │    │  │ 6. Fallback → price × 0.55 (45% margin estimate)        │   │      │   │
│   │    │  └─────────────────────────────────────────────────────────┘   │      │   │
│   │    └─────────────────────────────────────────────────────────────────┘      │   │
│   │                                                                              │   │
│   │    Financial Metrics:                                                        │   │
│   │    • total_cost = unit_cost × quantity                                      │   │
│   │    • gross_margin = revenue - total_cost                                    │   │
│   │    • gross_margin_pct = margin / revenue                                    │   │
│   │                                                                              │   │
│   └──────────────────────────────────┬──────────────────────────────────────────┘   │
│                                      │                                              │
│                                      ▼                                              │
│                      ┌───────────────────────────────────┐                         │
│                      │    fact_sales_margin.parquet      │                         │
│                      │    ~~~~~~~~~~~~~~~~~~~~~~~~~      │                         │
│                      │    2.3M rows with margin data     │                         │
│                      └───────────────────┬───────────────┘                         │
│                                          │                                          │
└──────────────────────────────────────────┼──────────────────────────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            AGGREGATION & ALERTING LAYER                              │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│   ┌────────────────────────┐  ┌────────────────────────┐  ┌──────────────────────┐ │
│   │ build_margin_summary   │  │ build_margin_alerts    │  │ build_cost_          │ │
│   │          .py           │  │          .py           │  │ sensitivity.py       │ │
│   │                        │  │                        │  │                      │ │
│   │ Groups by product/     │  │ Filters for:           │  │ Simulates:           │ │
│   │ bundle code            │  │ • margin < 30%         │  │ • +5% cost increase  │ │
│   │                        │  │ • sales ≥ 5000 MXN     │  │ • +10% cost increase │ │
│   └───────────┬────────────┘  └───────────┬────────────┘  └──────────┬───────────┘ │
│               │                           │                          │              │
│               ▼                           ▼                          ▼              │
│   ┌────────────────────┐      ┌────────────────────┐     ┌────────────────────┐    │
│   │ margin_summary.csv │      │ margin_alerts.csv  │     │cost_sensitivity.csv│    │
│   └────────────────────┘      └────────────────────┘     └────────────────────┘    │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            PRESENTATION LAYER (DASHBOARD)                            │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│                          Streamlit Multi-Page Application                            │
│                          ~~~~~~~~~~~~~~~~~~~~~~~~~~~~                                │
│                                                                                      │
│   ┌─────────────────────────────────────────────────────────────────────────────┐   │
│   │                              dashboard/app.py                                │   │
│   │                              (Landing Page)                                  │   │
│   └─────────────────────────────────────────────────────────────────────────────┘   │
│                                        │                                             │
│         ┌──────────────┬───────────────┼───────────────┬───────────────┐            │
│         ▼              ▼               ▼               ▼               ▼            │
│   ┌──────────┐  ┌───────────┐  ┌────────────┐  ┌─────────────┐  ┌───────────┐      │
│   │  1_Hoy   │  │2_Paquetes │  │3_Productos │  │4_Comparativo│  │5_2025_en_ │      │
│   │  (Today) │  │ (Bundles) │  │ (Products) │  │   (Trends)  │  │  corto    │      │
│   │          │  │           │  │            │  │             │  │ (2025 YTD)│      │
│   │• Daily   │  │• Bundle   │  │• Product   │  │• YTD        │  │• Current  │      │
│   │  Sales   │  │  Margin   │  │  Analytics │  │• Monthly    │  │  Year     │      │
│   │• WTD     │  │  Analysis │  │• Margin    │  │• Weekly     │  │  Summary  │      │
│   │• Top 5   │  │• Period   │  │  by Item   │  │• YoY        │  │           │      │
│   │  Margin  │  │  Filters  │  │            │  │             │  │           │      │
│   └──────────┘  └───────────┘  └────────────┘  └─────────────┘  └───────────┘      │
│                                                                                      │
│   Features:                                                                          │
│   • Mobile-first responsive design                                                   │
│   • @st.cache_data for Parquet caching                                              │
│   • Session state for filter persistence                                            │
│   • Custom HTML/CSS for metric cards                                                │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## Component Interaction

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          DATA DEPENDENCY GRAPH                                       │
└─────────────────────────────────────────────────────────────────────────────────────┘

                              dim_input_costs.csv
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
              recipe_items.csv    dim_drink_cost   bundle_components.csv
                    │                │                │
                    ▼                ▼                ▼
            product_unit_cost   expected_drink    bundle_unit_cost.csv
                    │           _cost.csv               │
                    │                │                  │
                    └────────────────┼──────────────────┘
                                     │
                    ┌────────────────┘
                    ▼
    fact_sales_raw.parquet  +  product_name_mapping.csv
                    │
                    ▼
           build_fact_sales_margin.py
                    │
                    ▼
           fact_sales_margin.parquet
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
  margin_summary.csv    cost_sensitivity.csv
          │
          ▼
  margin_alerts.csv
```

## Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Runtime** | Python 3.11 | Core language |
| **Environment** | Conda | Dependency management |
| **Data Processing** | pandas, pyarrow | DataFrame operations, Parquet I/O |
| **External Data** | gspread, google-auth | Google Sheets integration |
| **Configuration** | PyYAML | YAML config parsing |
| **Excel Handling** | openpyxl | POS file reading |
| **Dashboard** | Streamlit | Web-based visualization |
| **Version Control** | Git | Source control |

## Key Design Principles

1. **Immutability**: Raw data is never modified, only appended
2. **Fail-Fast**: Validation errors halt processing immediately
3. **Separation of Concerns**: Clear layer boundaries (ingestion → storage → analytics → presentation)
4. **Explicit Contracts**: YAML schemas define data expectations
5. **Auditability**: Cost estimation flags track data confidence
6. **Mobile-First**: Dashboard optimized for phone access during operations

## Security Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    SECURITY BOUNDARIES                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │              Google Cloud (External)                     │    │
│   │   • Service Account: astroburger-a7b14d51c891.json      │    │
│   │   • Scoped to specific spreadsheet                      │    │
│   │   • Read-only access                                    │    │
│   └─────────────────────────────────────────────────────────┘    │
│                            │                                      │
│                            ▼                                      │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │              Local System (Internal)                     │    │
│   │   • Credentials file excluded from git (.gitignore)     │    │
│   │   • Generated files excluded from git                   │    │
│   │   • No external network calls from dashboard            │    │
│   └─────────────────────────────────────────────────────────┘    │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```
