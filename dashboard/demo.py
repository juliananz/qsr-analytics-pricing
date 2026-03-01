"""
Demo mode: anonymize data for safe public/demo presentations.

Usage
-----
Set the environment variable DEMO_MODE=true before launching Streamlit.
When active, this module:
  - Shows a banner on every page
  - Replaces product/bundle names with generic labels (consistent per session)
  - Replaces employee/supplier names with generic labels
  - Scales all revenue and quantity figures by a fixed per-session random factor (0.8–1.2)
"""

import os
import random
import string

import pandas as pd
import streamlit as st

_DEMO: bool = os.getenv("DEMO_MODE", "").lower() == "true"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_demo_mode() -> bool:
    return _DEMO


def banner() -> None:
    """Render the demo-mode warning banner."""
    st.warning("Demo mode — data has been anonymized", icon="🔒")


def apply_margins(df: pd.DataFrame) -> pd.DataFrame:
    """Scale revenue/quantity columns and anonymize product names."""
    if not _DEMO or df.empty:
        return df
    _init_session()
    df = df.copy()
    k = st.session_state._demo_scaler
    for col in ("net_amount", "quantity", "gross_margin"):
        if col in df.columns:
            df[col] = df[col] * k
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
    if not _DEMO:
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
    if not _DEMO or df.empty:
        return df
    _init_session()
    df = df.copy()
    k = st.session_state._demo_scaler
    if "monto" in df.columns:
        df["monto"] = df["monto"] * k
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
    if not _DEMO or df.empty:
        return df
    _init_session()
    df = df.copy()
    k = st.session_state._demo_scaler
    for col in ("ventas_efectivo", "ventas_tarjeta", "ventas_app", "gastos_caja", "ventas_sistema"):
        if col in df.columns:
            df[col] = df[col] * k
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
    """Initialize demo state in st.session_state exactly once per session."""
    if "_demo_initialized" not in st.session_state:
        st.session_state._demo_initialized = True
        st.session_state._demo_scaler = random.uniform(0.8, 1.2)
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
