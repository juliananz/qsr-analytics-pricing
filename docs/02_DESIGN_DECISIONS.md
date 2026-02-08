# Design Decisions Document

## Executive Summary

This document captures the key design decisions made during the development of the QSR Analytics & Pricing System, including the trade-offs considered, alternatives evaluated, and rationale for final choices.

---

## Decision 1: File-Based Storage vs. Database

### Context
The system needs to store and query ~8 million sales transactions with daily updates.

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **SQLite** | SQL queries, ACID compliance, single file | Schema migrations, query complexity |
| **PostgreSQL** | Full RDBMS features, concurrent access | Infrastructure overhead, hosting costs |
| **Parquet Files** | Columnar compression, pandas-native, portable | No SQL, manual indexing |
| **CSV Files** | Human-readable, universal compatibility | No compression, slow for large data |

### Decision: Parquet for transactional data, CSV for reference data

### Rationale
- **Scale**: 8M rows is manageable in-memory with Parquet (~8MB compressed)
- **Portability**: No database infrastructure required for small business
- **Performance**: Columnar format optimizes dashboard read patterns
- **Simplicity**: pandas-native I/O eliminates ORM complexity
- **Reference Data**: CSV chosen for human editability (costs, recipes, mappings)

### Trade-offs Accepted
- No SQL query capabilities (requires pandas expressions)
- No concurrent write support (acceptable for single-user/batch updates)
- No transactions/rollback (mitigated by append-only design)

---

## Decision 2: Append-Only Immutability for Raw Data

### Context
POS transaction data needs to be reliable, auditable, and recoverable.

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **Mutable updates** | Simpler code, direct corrections | Audit trail loss, corruption risk |
| **Append-only** | Full history, easy rollback, auditability | Storage growth, rebuild complexity |
| **Event sourcing** | Complete state reconstruction | Over-engineering for this scale |

### Decision: Append-only with date-based deduplication

### Rationale
- **Auditability**: Business can trace any transaction to source
- **Recovery**: Any corruption can be fixed by rebuilding from POS exports
- **Simplicity**: Incremental append is simpler than merge logic
- **Scale**: 3 years of data is ~8MB; storage growth is negligible

### Trade-offs Accepted
- Cannot correct historical data without full rebuild
- Duplicate detection requires explicit date filtering
- Storage grows linearly (acceptable at current scale)

---

## Decision 3: Cost Resolution Waterfall

### Context
Products need unit costs for margin calculation, but data completeness varies.

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **Strict matching only** | High confidence | Many NaN costs, incomplete analysis |
| **Single fallback** | Simple logic | Inaccurate for varied product types |
| **Multi-level waterfall** | Handles all cases | Complex, requires maintenance |
| **ML-based estimation** | Potentially accurate | Over-engineering, black box |

### Decision: 6-level waterfall with explicit fallback tracking

```
1. Non-product revenue → cost = price (0% margin)
2. Bundle products → bundle_unit_cost lookup
3. Beverages → expected_drink_cost (weighted average)
4. Extra avocado → fixed cost (5.00 MXN)
5. Mapped products → product_unit_cost lookup
6. Fallback → 55% of price (assumes 45% target margin)
```

### Rationale
- **Completeness**: Every row gets a cost, enabling full margin analysis
- **Transparency**: `cost_estimated` flag tracks fallback usage
- **Business Logic**: Waterfall mirrors actual cost structure (bundles, drinks, individual items)
- **Conservatism**: 45% margin fallback is below business target, avoiding over-optimistic estimates

### Trade-offs Accepted
- Fallback estimates may be inaccurate for specific products
- Waterfall order matters and requires careful maintenance
- Complex business rules embedded in code (vs. configuration)

---

## Decision 4: Google Sheets Integration vs. Custom Forms

### Context
Daily cash closes (cortes) and expenses need to be captured by staff.

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **Custom web form** | Full control, validation | Development time, hosting |
| **Google Forms + Sheets** | Free, familiar to staff, mobile-friendly | External dependency, API limits |
| **Excel + email** | Simple | Manual processing, error-prone |
| **Mobile app** | Best UX | Significant development effort |

### Decision: Google Sheets with service account API access

### Rationale
- **Zero training**: Staff already familiar with Google Forms
- **Free**: No hosting or licensing costs
- **Reliable**: Google uptime exceeds custom infrastructure
- **Automation**: gspread API enables programmatic ingestion
- **Validation**: Server-side validation catches errors at ingestion

### Trade-offs Accepted
- External service dependency
- API rate limits (mitigated by batch fetch)
- Credential management complexity
- Limited input validation at form level

---

## Decision 5: Streamlit vs. Custom Dashboard

### Context
Business owners need mobile-accessible analytics dashboard.

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **Streamlit** | Rapid development, Python-native, free | Limited customization, server required |
| **Dash (Plotly)** | More flexibility, better charts | More complex, heavier |
| **React + API** | Full control, best UX | 10x development effort |
| **Power BI** | Enterprise features, familiar | Licensing cost, vendor lock-in |
| **Grafana** | Great for metrics | Requires time-series DB setup |

### Decision: Streamlit with custom HTML/CSS for mobile

### Rationale
- **Speed**: Dashboard built in days, not weeks
- **Integration**: Direct pandas DataFrame consumption
- **Caching**: Built-in @st.cache_data for Parquet performance
- **Cost**: Open source, deployable on minimal infrastructure
- **Mobile**: Custom HTML injection achieves responsive design

### Trade-offs Accepted
- Limited interactivity compared to React
- Requires running Python server (vs. static hosting)
- Session state management can be awkward
- Mobile experience requires CSS hacks

---

## Decision 6: Expected Drink Cost vs. Per-Drink Tracking

### Context
Bundles include a drink, but customers choose different drinks with different costs.

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **Track actual drink selection** | Perfect accuracy | Requires POS changes, complex bundle logic |
| **Fixed average cost** | Simple | Ignores purchase mix |
| **Weighted expected cost** | Reflects actual mix | Requires distribution data maintenance |
| **Highest cost assumption** | Conservative | Underestimates margins |

### Decision: Weighted expected cost based on purchase distribution

### Rationale
- **Accuracy**: Reflects actual customer behavior
- **Maintainability**: Distribution data updated periodically
- **Simplicity**: Single cost per bundle (no per-transaction complexity)
- **Transparency**: Methodology is auditable and explainable

### Trade-offs Accepted
- Requires periodic distribution updates
- Cannot track individual bundle profitability variations
- Historical data uses current distribution (not historical)

---

## Decision 7: Fail-Fast Validation vs. Partial Processing

### Context
Data quality issues can occur in source files and Google Sheets.

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **Fail-fast** | Data integrity guaranteed | Pipeline halts on any error |
| **Partial processing** | More data captured | Silent data quality issues |
| **Quarantine bad records** | Best of both | Complex implementation |
| **Warn and continue** | Pipeline resilient | Bad data in outputs |

### Decision: Fail-fast with detailed error messages

### Rationale
- **Data Integrity**: Bad data is worse than no data for business decisions
- **Debugging**: Clear errors pinpoint issues immediately
- **Trust**: Users can trust outputs are validated
- **Simplicity**: No quarantine infrastructure needed

### Trade-offs Accepted
- Single bad record blocks entire ingestion
- Manual intervention required to fix source data
- No partial day data (all or nothing)

---

## Decision 8: Single-Tenant vs. Multi-Tenant Design

### Context
System initially built for one restaurant (Astro Burger).

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **Single-tenant** | Simple, fast development | Cannot serve multiple businesses |
| **Multi-tenant** | Scalable, SaaS potential | Complex, over-engineered for now |
| **Configurable tenant** | Extensible via config | Middle complexity |

### Decision: Single-tenant with business_id in configuration

### Rationale
- **YAGNI**: No current need for multiple businesses
- **Speed**: Ship valuable features now, refactor if needed
- **Configuration**: business.yaml allows future extension
- **Isolation**: Single business means simpler security model

### Trade-offs Accepted
- Cannot serve multiple businesses without code changes
- Some generic abstractions may be wasted if never multi-tenant
- Database would be required for true multi-tenancy

---

## Decision 9: Manual Reference Data vs. Admin Interface

### Context
Product costs, recipes, and mappings need periodic updates.

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **CSV files (manual)** | Simple, version controlled | No validation at edit time |
| **Admin web interface** | Validation, user-friendly | Development effort |
| **Excel with macros** | Familiar to business | Sync complexity |
| **Database with UI** | Full CRUD | Infrastructure overhead |

### Decision: CSV files with git version control

### Rationale
- **Auditability**: Git tracks all changes with timestamps
- **Simplicity**: No additional infrastructure
- **Familiarity**: Business users can edit in Excel, save as CSV
- **Validation**: Pipeline validates on load (fail-fast)
- **Recovery**: Any mistake reversible via git

### Trade-offs Accepted
- No input validation until pipeline runs
- Requires git knowledge for rollback
- No concurrent edit protection
- Format errors possible (encoding, delimiters)

---

## Decision 10: Synchronous vs. Scheduled Pipeline

### Context
Pipeline needs to process daily data and refresh dashboard.

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **Manual trigger** | Full control | Requires human action |
| **Cron/Task Scheduler** | Automated, reliable | Setup complexity, error monitoring |
| **Event-driven (file watch)** | Real-time processing | Complexity, false triggers |
| **On-demand via dashboard** | User-driven refresh | Slower first load |

### Decision: Manual trigger via run_pipeline.py

### Rationale
- **Control**: Business controls when processing happens
- **Simplicity**: No scheduler infrastructure needed
- **Debugging**: Easier to troubleshoot manual runs
- **Volume**: Daily updates don't require real-time processing

### Trade-offs Accepted
- Requires daily manual execution
- Dashboard may show stale data
- No alerting for missed runs

---

## Summary of Key Trade-offs

| Decision | Chosen Simplicity | Sacrificed Capability |
|----------|-------------------|----------------------|
| File storage | No database setup | SQL queries, transactions |
| Append-only | Easy recovery | In-place corrections |
| Cost waterfall | Complete coverage | Perfect accuracy |
| Google Sheets | Free, familiar | Full control |
| Streamlit | Rapid development | Custom UX |
| Expected drink cost | Simple bundles | Per-selection tracking |
| Fail-fast | Data integrity | Partial processing |
| Single-tenant | Fast delivery | Multi-business scale |
| CSV reference data | Version control | Edit-time validation |
| Manual pipeline | Simple operations | Automated scheduling |

---

## Future Considerations

If the system needs to scale, these decisions should be revisited:

1. **Database**: If queries become complex or data exceeds 100M rows
2. **Multi-tenant**: If serving multiple restaurants becomes a requirement
3. **Scheduling**: If daily manual execution becomes a burden
4. **Real-time**: If live sales monitoring is needed
5. **Admin UI**: If reference data updates become frequent
