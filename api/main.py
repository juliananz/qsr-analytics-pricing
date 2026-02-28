"""
QSR Analytics API
=================
Serves aggregated sales and margin data from the pipeline parquet.

Start with:
    uvicorn api.main:app --reload
"""

from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

PARQUET_PATH = Path("data/analytics/fact_sales_margin.parquet")

app = FastAPI(title="QSR Analytics API")


# ============================================================
# Response models
# ============================================================

class HealthResponse(BaseModel):
    status: str          # "ok" | "stale"
    last_update: str     # ISO date string, e.g. "2026-02-28"
    days_stale: int


class DailyRecord(BaseModel):
    sale_date: str
    revenue: float
    gross_margin: float
    transactions: int
    margin_pct: float


class ProductMargin(BaseModel):
    product_name: str
    revenue: float
    gross_margin: float
    transactions: int
    margin_pct: float


# ============================================================
# Data loading
# ============================================================

def _load() -> pd.DataFrame:
    return pd.read_parquet(PARQUET_PATH)


def _require_parquet() -> pd.DataFrame:
    if not PARQUET_PATH.exists():
        raise HTTPException(status_code=503, detail="Data file not available")
    return _load()


# ============================================================
# Endpoints
# ============================================================

@app.get("/health", response_model=HealthResponse)
def health():
    if not PARQUET_PATH.exists():
        return HealthResponse(status="stale", last_update="", days_stale=-1)
    df = pd.read_parquet(PARQUET_PATH, columns=["sale_date"])
    last_update: date = df["sale_date"].max().date()
    days_stale = (date.today() - last_update).days
    return HealthResponse(
        status="ok" if days_stale <= 1 else "stale",
        last_update=str(last_update),
        days_stale=days_stale,
    )


@app.get("/summary/daily", response_model=list[DailyRecord])
def summary_daily(days: int = Query(30, ge=1, le=365)):
    df = _require_parquet()
    cutoff = date.today() - timedelta(days=days)
    df = df[df["sale_date"].dt.date >= cutoff]
    grouped = (
        df.groupby("sale_date")
        .agg(
            revenue=("net_amount", "sum"),
            gross_margin=("gross_margin", "sum"),
            transactions=("net_amount", "count"),
        )
        .reset_index()
        .sort_values("sale_date")
    )
    grouped["margin_pct"] = (
        grouped["gross_margin"] / grouped["revenue"].replace(0.0, float("nan"))
    ).fillna(0.0)
    grouped["sale_date"] = grouped["sale_date"].dt.strftime("%Y-%m-%d")
    return grouped.to_dict(orient="records")


@app.get("/margins/by-product", response_model=list[ProductMargin])
def margins_by_product(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    df = _require_parquet()
    df = df[~df["non_product_revenue"]]
    if start_date:
        df = df[df["sale_date"] >= pd.Timestamp(start_date)]
    if end_date:
        df = df[df["sale_date"] <= pd.Timestamp(end_date)]
    grouped = (
        df.groupby("product_name")
        .agg(
            revenue=("net_amount", "sum"),
            gross_margin=("gross_margin", "sum"),
            transactions=("net_amount", "count"),
        )
        .reset_index()
        .sort_values("gross_margin", ascending=False)
        .head(20)
    )
    grouped["margin_pct"] = (
        grouped["gross_margin"] / grouped["revenue"].replace(0.0, float("nan"))
    ).fillna(0.0)
    return grouped.to_dict(orient="records")
