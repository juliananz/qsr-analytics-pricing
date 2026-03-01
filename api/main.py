"""
QSR Analytics API
=================
Serves aggregated sales and margin data from the pipeline parquet.

Start with:
    uvicorn api.main:app --reload
"""

import os
import string
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

_DEMO: bool = os.getenv("DEMO_MODE", "").lower() == "true"
_DATA_DIR = Path("data/demo") if _DEMO else Path("data/analytics")
PARQUET_PATH = _DATA_DIR / "fact_sales_margin.parquet"

# Stable product-name → generic-label mapping, built once at startup.
# Mirrors the logic in dashboard/demo.py so labels are identical.
_PRODUCT_MAP: dict[str, str] = {}


def _letter(n: int) -> str:
    """0→A, 1→B, …, 25→Z, 26→AA, … (mirrors demo.py)"""
    result = ""
    n += 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = string.ascii_uppercase[rem] + result
    return result


def _build_product_map(df: pd.DataFrame) -> None:
    """Populate _PRODUCT_MAP from all unique product names (sorted).

    Called at startup so every request gets the same mapping regardless
    of which date range is queried.
    """
    global _PRODUCT_MAP
    if _PRODUCT_MAP:
        return
    _PRODUCT_MAP = {
        name: f"Producto {_letter(i)}"
        for i, name in enumerate(sorted(df["product_name"].dropna().unique()))
    }


app = FastAPI(title="QSR Analytics API")


@app.on_event("startup")
def _debug_parquet() -> None:
    """Print first 5 rows on startup so the data shape is visible in logs."""
    if PARQUET_PATH.exists():
        df = pd.read_parquet(PARQUET_PATH)
        print("\n=== fact_sales_margin — first 5 rows ===")
        print(df.head().to_string())
        print(f"shape: {df.shape}  |  sale_date range: {df['sale_date'].min().date()} → {df['sale_date'].max().date()}\n")
        if _DEMO:
            _build_product_map(df)
            print(f"DEMO_MODE active — {len(_PRODUCT_MAP)} products mapped\n")


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
    # Anchor to the data's own max date so the endpoint returns real rows
    # even when the pipeline hasn't run recently.
    max_date = df["sale_date"].max()
    cutoff = max_date - pd.Timedelta(days=days)
    df = df[df["sale_date"] >= cutoff]
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
    if _DEMO:
        # Build map lazily in case startup didn't run (e.g. tests / direct calls)
        _build_product_map(df)
        grouped["product_name"] = (
            grouped["product_name"].map(_PRODUCT_MAP).fillna(grouped["product_name"])
        )
    return grouped.to_dict(orient="records")
