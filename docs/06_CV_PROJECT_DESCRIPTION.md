# Project Description for CV/Interview

## One-Line Summary

**End-to-end analytics platform for a quick-service restaurant, processing 8M+ transactions to deliver real-time margin insights via a mobile-first dashboard.**

---

## Short Description (50 words)

Built a data pipeline and analytics system for a Mexican QSR business. Ingests POS data and Google Sheets inputs, applies cost-based margin calculations with a 6-level resolution algorithm, and presents insights through a Streamlit dashboard. Handles 8M+ historical transactions with daily incremental updates.

---

## Medium Description (150 words)

Designed and implemented a complete analytics solution for Astro Burger, a quick-service restaurant in Mexico. The system processes 3+ years of point-of-sale data (8M transactions) to calculate product-level profitability and identify margin optimization opportunities.

**Key Technical Achievements:**
- Built an ETL pipeline that normalizes POS exports and enriches transactions with cost data using a 6-level resolution waterfall (bundles → beverages → recipes → fallback estimation)
- Implemented append-only data architecture with Parquet storage for efficient columnar queries
- Integrated Google Sheets via service account API for daily cash close reconciliation
- Created a mobile-first Streamlit dashboard with custom HTML/CSS for operational monitoring

**Business Impact:**
- Enabled daily margin tracking where none existed before
- Identified low-margin products for pricing adjustments
- Provided cost sensitivity analysis for supplier negotiation
- Reduced manual reporting effort from hours to minutes

---

## Extended Description (For Technical Interviews)

### Project Overview

I built a full-stack analytics platform for a small restaurant business that needed visibility into product-level profitability. The business had 3+ years of POS transaction data but no way to analyze margins or identify pricing opportunities.

### Technical Architecture

**Data Pipeline:**
- Ingestion layer processes Excel POS exports with schema validation
- Incremental append strategy prevents data duplication
- Google Sheets integration for daily cash closes using gspread API
- YAML-based configuration for data contracts and business rules

**Cost Resolution System:**
- Designed a 6-level waterfall algorithm to assign costs to every transaction
- Recipe-based costing for made-to-order items (burgers, tacos)
- Bundle decomposition for combo meals with weighted expected drink costs
- Fallback estimation (55% of price) for unmapped products with tracking flags

**Storage Strategy:**
- Apache Parquet for transactional data (8M rows in 8MB)
- CSV for reference data (costs, recipes, mappings) for human editability
- Append-only immutability for audit trail and easy recovery

**Dashboard:**
- Streamlit multi-page application
- Custom HTML injection for mobile-responsive metric cards
- Caching layer for sub-second dashboard loads
- Date range filters with session state persistence

### Key Design Decisions

1. **File-based over database**: Chose Parquet files over SQLite/PostgreSQL because the data volume (8M rows) fits in memory, the access pattern is analytical (batch reads), and the business doesn't need concurrent writes or SQL. Trade-off: no query optimization, but pandas handles the workload.

2. **Fail-fast validation**: Pipeline halts on any validation error rather than processing partial data. This ensures business decisions are based on complete, validated information.

3. **Cost estimation transparency**: Every transaction has a `cost_estimated` flag indicating whether the cost came from actual data or fallback estimation. This allows the business to prioritize which products need cost verification.

4. **Waterfall resolution**: The 6-level cost resolution handles the messy reality of restaurant data—combos, drinks, specials, adjustments—in a deterministic, auditable way.

### Technologies Used

- **Python 3.11** - Core language
- **pandas / pyarrow** - Data processing and Parquet I/O
- **Streamlit** - Dashboard framework
- **gspread / google-auth** - Google Sheets API integration
- **PyYAML** - Configuration management
- **Git** - Version control

### Metrics & Impact

| Metric | Value |
|--------|-------|
| Transactions processed | 8+ million |
| Historical coverage | 3+ years |
| Daily incremental processing | ~30 seconds |
| Cost coverage | 89% known, 11% estimated |
| Dashboard load time | <2 seconds |

### What I Would Do Differently

1. **Add unit tests**: The current system relies on audit summaries and manual verification. A proper test suite would catch regressions.

2. **Implement scheduling**: Currently manual pipeline execution; would add cron/Task Scheduler for automation.

3. **Database for scale**: If the business grows to multiple locations, I'd migrate to PostgreSQL with proper partitioning.

---

## Behavioral Interview Points

### Problem Solving

> "Tell me about a time you had to design a system with incomplete requirements."

The business owner knew they wanted "margin analysis" but couldn't specify exactly what that meant. I started by understanding the raw data (POS exports), identified what was possible (transaction-level margins), and iteratively built features. The 6-level cost waterfall emerged from discovering that products fell into categories (bundles, individual items, beverages) that each needed different cost logic.

### Technical Decision Making

> "Describe a technical trade-off you made and why."

I chose file-based storage (Parquet) over a database. Pros: zero infrastructure, portable, version-controllable, pandas-native. Cons: no SQL, no concurrent writes. The decision fit this use case—single user, batch processing, analytical queries—and could be revisited if requirements change.

### Business Impact

> "How did your work create value for the business?"

Before this system, the owner had no idea which products were profitable. After deployment, they discovered that certain combos had <30% margins (below the 45% target) due to underpriced drink inclusions. This led to a menu redesign that improved average margin by 5 percentage points.

### Handling Ambiguity

> "How did you handle data quality issues?"

POS data had inconsistent product names ("Hamburguesa Queso" vs "HAMBURGUESA C/QUESO" vs "burger cheese"). Rather than manual cleanup, I built a mapping system that normalizes names to canonical product codes. The mapping file is version-controlled and easily updated when new variations appear.

---

## Skills Demonstrated

| Skill Category | Specific Skills |
|----------------|-----------------|
| **Data Engineering** | ETL pipelines, schema validation, incremental processing, data modeling |
| **Python** | pandas, type coercion, file I/O, API integration |
| **Analytics** | Margin calculation, cost allocation, sensitivity analysis |
| **Visualization** | Streamlit dashboards, mobile-responsive design |
| **Architecture** | Layered design, configuration management, data contracts |
| **Business Acumen** | Understanding restaurant operations, translating requirements |

---

## Questions to Expect

1. **Why Parquet over CSV for large data?**
   - Columnar format: read only needed columns
   - Compression: 8MB vs ~50MB CSV
   - Type preservation: dates/numerics stored correctly
   - Fast I/O: pyarrow is highly optimized

2. **How do you handle late-arriving data?**
   - Incremental ingestion compares dates
   - Only new dates are appended
   - Full rebuild available if corrections needed

3. **What happens if Google Sheets auth fails?**
   - Fail-fast: pipeline stops, no partial data
   - Clear error message with troubleshooting steps
   - Credentials refresh procedure documented

4. **How would you scale this to 100 restaurants?**
   - Add business_id partitioning
   - Move to PostgreSQL for concurrent access
   - Deploy dashboard to cloud (Streamlit Cloud or AWS)
   - Add authentication and access control

5. **Why Streamlit over Dash or React?**
   - Development speed: built in days, not weeks
   - Python-native: no context switching
   - Sufficient for single-business use case
   - Would consider React for multi-tenant SaaS
