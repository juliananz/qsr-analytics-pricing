# Deployment and Monitoring Plan

## Overview

This document describes the deployment architecture, operational procedures, and monitoring strategy for the QSR Analytics & Pricing System.

---

## Deployment Architecture

### Current Architecture (Local Deployment)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           LOCAL DEPLOYMENT                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────────┐      ┌─────────────────────┐                     │
│   │   Windows Machine   │      │   Google Cloud      │                     │
│   │                     │      │                     │                     │
│   │  ┌───────────────┐  │      │  ┌───────────────┐  │                     │
│   │  │ Python 3.11   │  │ ───► │  │ Google Sheets │  │                     │
│   │  │ Conda Env     │  │      │  │ (Cortes,      │  │                     │
│   │  └───────────────┘  │      │  │  Gastos)      │  │                     │
│   │         │           │      │  └───────────────┘  │                     │
│   │         ▼           │      │                     │                     │
│   │  ┌───────────────┐  │      └─────────────────────┘                     │
│   │  │ Data Pipeline │  │                                                   │
│   │  │ (scripts/)    │  │                                                   │
│   │  └───────────────┘  │                                                   │
│   │         │           │                                                   │
│   │         ▼           │                                                   │
│   │  ┌───────────────┐  │      ┌─────────────────────┐                     │
│   │  │ Streamlit     │  │ ───► │   Mobile Browser    │                     │
│   │  │ Dashboard     │  │      │   (Business User)   │                     │
│   │  │ :8501         │  │      └─────────────────────┘                     │
│   │  └───────────────┘  │                                                   │
│   │                     │                                                   │
│   └─────────────────────┘                                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Recommended Production Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PRODUCTION DEPLOYMENT                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                        Cloud Provider (AWS/GCP/Azure)                │   │
│   │                                                                      │   │
│   │   ┌─────────────────┐    ┌─────────────────┐    ┌──────────────┐   │   │
│   │   │  Compute        │    │  Storage        │    │  Scheduler   │   │   │
│   │   │  (EC2/VM)       │    │  (S3/GCS)       │    │  (CloudWatch │   │   │
│   │   │                 │    │                 │    │   /Cron)     │   │   │
│   │   │  • Pipeline     │    │  • Parquet      │    │              │   │   │
│   │   │  • Dashboard    │    │  • CSV          │    │  Daily 6am   │   │   │
│   │   │                 │    │  • Backups      │    │              │   │   │
│   │   └────────┬────────┘    └────────┬────────┘    └──────┬───────┘   │   │
│   │            │                      │                    │           │   │
│   │            └──────────────────────┼────────────────────┘           │   │
│   │                                   │                                 │   │
│   └───────────────────────────────────┼─────────────────────────────────┘   │
│                                       │                                      │
│                                       ▼                                      │
│   ┌───────────────────────────────────────────────────────────────────────┐ │
│   │                          External Services                             │ │
│   │   ┌─────────────────┐    ┌─────────────────┐    ┌──────────────────┐  │ │
│   │   │  Google Sheets  │    │  Monitoring     │    │  Notifications   │  │ │
│   │   │  (Data Input)   │    │  (CloudWatch/   │    │  (SNS/Email)     │  │ │
│   │   │                 │    │   Datadog)      │    │                  │  │ │
│   │   └─────────────────┘    └─────────────────┘    └──────────────────┘  │ │
│   └───────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Environment Setup

### Local Development

```bash
# 1. Clone repository
git clone <repository-url>
cd qsr-analytics-pricing

# 2. Create conda environment
conda env create -f environment.yml
conda activate qsr_analytics

# 3. Configure Google Sheets credentials
# Place service account JSON at path specified in config/sheets.yaml

# 4. Verify installation
python -c "import pandas; import streamlit; print('OK')"
```

### Environment Configuration

**environment.yml**:
```yaml
name: qsr_analytics
channels:
  - defaults
  - conda-forge
dependencies:
  - python=3.11
  - pandas>=1.5
  - pyarrow>=10.0
  - openpyxl>=3.0
  - pyyaml>=6.0
  - streamlit>=1.20
  - gspread>=5.0
  - google-auth>=2.0
```

### Configuration Files

| File | Purpose | Secrets |
|------|---------|---------|
| `config/business.yaml` | Business constants | No |
| `config/schema.yaml` | Data contracts | No |
| `config/sheets.yaml` | Google Sheets config | Yes (credentials path) |

### Secrets Management

**Current (Local)**:
- Service account JSON stored on local filesystem
- Path configured in `config/sheets.yaml`
- File excluded from git via `.gitignore`

**Recommended (Production)**:
```bash
# Use environment variables
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json

# Or use cloud secrets manager
# AWS Secrets Manager / GCP Secret Manager / Azure Key Vault
```

---

## Operational Procedures

### Daily Operations

#### 1. Export POS Data (Manual)

```
Time: After business closes (typically 10pm-11pm)
Actor: Business staff

Steps:
1. Open POS system
2. Export daily sales to Excel
3. Save as data/raw_data/comandas.xlsx
4. Overwrite existing file
```

#### 2. Run Pipeline (Manual/Scheduled)

```bash
# Manual execution
python run_pipeline.py

# Expected output:
# [INFO] Loading incremental sales...
# [INFO] Added 234 new transactions
# [INFO] Building margin calculations...
# [INFO] Generating summaries...
# [INFO] Pipeline complete

# Check for errors in output
```

#### 3. Start Dashboard (If not running)

```bash
streamlit run dashboard/app.py

# Access at http://localhost:8501
# Or via network: http://<machine-ip>:8501
```

#### 4. Verify Data Freshness

- Open dashboard
- Check "Hoy" page shows current date
- Verify metrics are reasonable

### Weekly Operations

#### 1. Review Margin Alerts

```bash
# Check alerts file
cat data/analytics/margin_alerts.csv

# Review low-margin products
# Take action: adjust prices or investigate costs
```

#### 2. Update Product Mappings (If Needed)

```bash
# If new products appear in fallback estimation
# Edit: data/processed_data/product_name_mapping.csv
# Add: raw_name,product_code mapping
```

#### 3. Backup Data

```bash
# Create timestamped backup
$date = Get-Date -Format "yyyy-MM-dd"
Copy-Item -Recurse data/analytics "backups/analytics_$date"
Copy-Item -Recurse data/processed_data "backups/processed_$date"
```

### Monthly Operations

#### 1. Update Ingredient Costs

```bash
# Edit: data/processed_data/dim_input_costs.csv
# Update unit_cost for changed ingredients

# Rebuild derived costs
python scripts/build_product_unit_cost.py
python scripts/build_bundle_cost.py

# Rebuild margins with new costs
python scripts/build_fact_sales_margin.py
```

#### 2. Full Historical Rebuild (Optional)

```bash
# If data corrections needed
python run_pipeline.py --rebuild-sales
```

#### 3. Review Cost Sensitivity

```bash
# Analyze impact of potential cost increases
cat data/analytics/cost_sensitivity.csv
```

---

## Monitoring Strategy

### Health Checks

#### Data Freshness Check

```python
# monitoring/health_check.py
import pandas as pd
from datetime import datetime, timedelta

def check_data_freshness():
    df = pd.read_parquet('data/analytics/fact_sales_margin.parquet')
    last_date = df['sale_date'].max()
    days_stale = (pd.Timestamp.today() - last_date).days

    status = {
        'last_update': str(last_date.date()),
        'days_stale': days_stale,
        'healthy': days_stale <= 1
    }

    return status
```

#### Pipeline Status Check

```python
def check_pipeline_outputs():
    required_files = [
        'data/analytics/fact_sales_raw.parquet',
        'data/analytics/fact_sales_margin.parquet',
        'data/analytics/margin_summary.csv',
    ]

    status = {}
    for f in required_files:
        path = Path(f)
        status[f] = {
            'exists': path.exists(),
            'modified': datetime.fromtimestamp(path.stat().st_mtime) if path.exists() else None,
            'size_mb': path.stat().st_size / 1024 / 1024 if path.exists() else 0
        }

    return status
```

### Key Metrics to Monitor

| Metric | Check Frequency | Alert Threshold |
|--------|-----------------|-----------------|
| Data freshness | Daily | >1 day stale |
| Pipeline execution | After each run | Any failure |
| Cost coverage | Daily | <80% |
| Average margin | Weekly | <35% or >55% |
| Low-margin products | Weekly | New alerts |
| Dashboard uptime | Continuous | Any downtime |

### Alerting (Recommended Implementation)

```python
# monitoring/alerts.py
import smtplib
from email.message import EmailMessage

def send_alert(subject, body):
    """Send email alert for critical issues"""
    msg = EmailMessage()
    msg['Subject'] = f"[QSR Analytics] {subject}"
    msg['From'] = "alerts@example.com"
    msg['To'] = "owner@example.com"
    msg.set_content(body)

    # Configure SMTP server
    # with smtplib.SMTP('smtp.example.com') as server:
    #     server.send_message(msg)

    print(f"ALERT: {subject}\n{body}")

def check_and_alert():
    """Run all health checks and alert on issues"""

    # Check data freshness
    freshness = check_data_freshness()
    if freshness['days_stale'] > 1:
        send_alert(
            "Data Stale",
            f"Last update: {freshness['last_update']}\n"
            f"Days stale: {freshness['days_stale']}"
        )

    # Check cost coverage
    df = pd.read_parquet('data/analytics/fact_sales_margin.parquet')
    coverage = (~df['cost_estimated']).mean()
    if coverage < 0.80:
        send_alert(
            "Low Cost Coverage",
            f"Current coverage: {coverage:.1%}\n"
            f"Threshold: 80%"
        )

    # Check for new margin alerts
    alerts = pd.read_csv('data/analytics/margin_alerts.csv')
    if len(alerts) > 0:
        send_alert(
            f"{len(alerts)} Low-Margin Products",
            alerts.to_string()
        )
```

### Logging

#### Pipeline Logging

```python
# Recommended logging configuration
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('logs/pipeline.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Usage in scripts
logger.info("Starting margin calculation...")
logger.warning(f"Using fallback cost for {product_name}")
logger.error(f"Failed to process file: {filename}")
```

#### Log Retention

```bash
# Rotate logs weekly, keep 4 weeks
# Add to scheduled tasks / cron

# Windows (PowerShell)
Get-ChildItem logs/*.log | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-28)} | Remove-Item

# Linux
find logs/ -name "*.log" -mtime +28 -delete
```

---

## Disaster Recovery

### Backup Strategy

| Data Type | Frequency | Retention | Location |
|-----------|-----------|-----------|----------|
| Raw POS files | Daily | 1 year | `backups/raw/` |
| Processed data | Weekly | 3 months | `backups/processed/` |
| Analytics outputs | Weekly | 1 month | `backups/analytics/` |
| Configuration | On change | Forever | Git repository |

### Recovery Procedures

#### Scenario 1: Corrupted Analytics Output

```bash
# Rebuild from raw data
python run_pipeline.py --rebuild-sales
```

#### Scenario 2: Lost Raw Data

```bash
# Restore from backup
Copy-Item backups/raw/latest/* data/raw_data/

# Or re-export from POS system
```

#### Scenario 3: Configuration Error

```bash
# Restore from git
git checkout HEAD -- config/
```

#### Scenario 4: Full System Recovery

```bash
# 1. Clone repository
git clone <repository-url>

# 2. Restore environment
conda env create -f environment.yml

# 3. Restore data from backups
Copy-Item -Recurse backups/latest/raw_data data/
Copy-Item -Recurse backups/latest/processed_data data/

# 4. Rebuild analytics
python run_pipeline.py --rebuild-sales

# 5. Verify dashboard
streamlit run dashboard/app.py
```

---

## Scaling Considerations

### Current Limits

| Resource | Current | Limit |
|----------|---------|-------|
| Transaction rows | 8M | ~100M (memory) |
| Daily new rows | ~1K | ~100K |
| Concurrent users | 1-5 | ~10 (Streamlit) |
| Storage | 10MB | Local disk |

### When to Scale

Consider infrastructure upgrade when:
- Transaction volume exceeds 50M rows
- Multiple restaurants need separate dashboards
- Real-time updates required
- >10 concurrent dashboard users

### Scaling Options

1. **Database Migration**: Move to PostgreSQL for >100M rows
2. **Cloud Hosting**: Deploy Streamlit to Streamlit Cloud or AWS
3. **Multi-tenant**: Add business_id partitioning
4. **Caching Layer**: Add Redis for dashboard performance
5. **Job Queue**: Add Celery for async pipeline execution

---

## Runbook Summary

### Quick Reference

```bash
# Daily pipeline
python run_pipeline.py

# Full rebuild
python run_pipeline.py --rebuild-sales

# Start dashboard
streamlit run dashboard/app.py

# Check data freshness
python -c "import pandas as pd; print(pd.read_parquet('data/analytics/fact_sales_margin.parquet')['sale_date'].max())"

# View margin alerts
type data\analytics\margin_alerts.csv

# Update costs and rebuild
python scripts/build_product_unit_cost.py && python scripts/build_fact_sales_margin.py
```

### Emergency Contacts

| Issue | Contact | Action |
|-------|---------|--------|
| Pipeline failure | Developer | Check logs, re-run |
| Data quality issue | Business owner | Verify POS export |
| Dashboard down | Developer | Restart Streamlit |
| Google Sheets auth | Developer | Refresh credentials |
