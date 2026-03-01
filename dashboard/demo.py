"""
Demo mode: anonymize data for safe public/demo presentations.

Usage (local)
-------------
DEMO_MODE=true streamlit run dashboard/app.py

Usage (Streamlit Community Cloud)
----------------------------------
In the app's Secrets section add:  DEMO_MODE = "true"

When active, this module:
  - Shows a banner on every page
  - Replaces product/bundle names with generic labels (consistent per session)
  - Replaces employee/supplier names with generic labels
  - Divides all revenue and quantity figures by a constant factor of 13
"""

import os
import string

import pandas as pd
import streamlit as st

# Constant divisor applied to all monetary and quantity figures in demo mode
_SCALER: float = 1 / 13

# Fast path: env var is available at import time
_DEMO_ENV: bool = os.getenv("DEMO_MODE", "").lower() == "true"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_demo_mode() -> bool:
    """Return True if DEMO_MODE is active (env var or Streamlit secret)."""
    if _DEMO_ENV:
        return True
    # Fallback: Streamlit Community Cloud exposes secrets via st.secrets,
    # not as OS environment variables.
    try:
        return str(st.secrets.get("DEMO_MODE", "")).lower() == "true"
    except Exception:
        return False


def banner() -> None:
    """Render the demo-mode warning banner."""
    st.warning("Demo mode — data has been anonymized", icon="🔒")


def apply_margins(df: pd.DataFrame) -> pd.DataFrame:
    """Scale revenue/quantity columns and anonymize product names."""
    if not is_demo_mode() or df.empty:
        return df
    _init_session()
    df = df.copy()
    for col in ("net_amount", "quantity", "gross_margin"):
        if col in df.columns:
            df[col] = df[col] * _SCALER
    if "product_name" in df.columns:
        _ensure_mapped(
            df["product_name"].dropna().unique(),
            st.session_state._demo_product_map,
            prefix="Producto",
            use_letter=True,
        )
        df["product_name"] = (
            df["product_name"]
            .map(st.session_state._demo_product_map)
            .fillna(df["product_name"])
        )
    return df


def apply_bundle_names(bundle_dict: dict) -> dict:
    """Anonymize a {bundle_code: display_name} mapping dict."""
    if not is_demo_mode():
        return bundle_dict
    _init_session()
    _ensure_mapped(
        bundle_dict.values(),
        st.session_state._demo_bundle_map,
        prefix="Paquete",
    )
    return {
        code: st.session_state._demo_bundle_map.get(name, name)
        for code, name in bundle_dict.items()
    }


def apply_gastos(df: pd.DataFrame) -> pd.DataFrame:
    """Scale monto and anonymize descripcion/proveedor in gastos."""
    if not is_demo_mode() or df.empty:
        return df
    _init_session()
    df = df.copy()
    if "monto" in df.columns:
        df["monto"] = df["monto"] * _SCALER
    if "descripcion" in df.columns:
        is_employee = (
            df.get("categoria", pd.Series("", index=df.index))
            .str.contains("Empleado|Mano de obra", case=False, na=False)
        )
        _ensure_mapped(
            df.loc[is_employee, "descripcion"].dropna().unique(),
            st.session_state._demo_person_map,
            prefix="Empleado",
        )
        _ensure_mapped(
            df.loc[~is_employee, "descripcion"].dropna().unique(),
            st.session_state._demo_gasto_map,
            prefix="Gasto",
        )
        # person_map takes priority over gasto_map for lookup
        combined = {**st.session_state._demo_gasto_map, **st.session_state._demo_person_map}
        df["descripcion"] = df["descripcion"].map(combined).fillna(df["descripcion"])
    if "proveedor" in df.columns:
        _ensure_mapped(
            df["proveedor"].dropna().unique(),
            st.session_state._demo_supplier_map,
            prefix="Proveedor",
        )
        df["proveedor"] = (
            df["proveedor"]
            .map(st.session_state._demo_supplier_map)
            .fillna(df["proveedor"])
        )
    return df


def apply_cortes(df: pd.DataFrame) -> pd.DataFrame:
    """Scale all monetary figures in cortes."""
    if not is_demo_mode() or df.empty:
        return df
    _init_session()
    df = df.copy()
    for col in ("ventas_efectivo", "ventas_tarjeta", "ventas_app", "gastos_caja", "ventas_sistema"):
        if col in df.columns:
            df[col] = df[col] * _SCALER
    return df


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _letter(n: int) -> str:
    """Map 0→A, 1→B, …, 25→Z, 26→AA, 27→AB, …"""
    result = ""
    n += 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = string.ascii_uppercase[rem] + result
    return result


def _init_session() -> None:
    """Initialize demo name-mapping dicts in session_state once per session."""
    if "_demo_initialized" not in st.session_state:
        st.session_state._demo_initialized = True
        st.session_state._demo_product_map: dict[str, str] = {}
        st.session_state._demo_bundle_map: dict[str, str] = {}
        st.session_state._demo_person_map: dict[str, str] = {}
        st.session_state._demo_gasto_map: dict[str, str] = {}
        st.session_state._demo_supplier_map: dict[str, str] = {}


def _ensure_mapped(
    names,
    mapping: dict,
    prefix: str,
    use_letter: bool = False,
) -> None:
    """Add any unseen names to *mapping* with the next available label."""
    for name in sorted(names):
        if name not in mapping:
            n = len(mapping)
            label = f"Producto {_letter(n)}" if use_letter else f"{prefix} {n + 1}"
            mapping[name] = label
