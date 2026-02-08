import streamlit as st
import pandas as pd
from datetime import timedelta

st.set_page_config(page_title="Productos", layout="centered")

from auth import require_auth
require_auth()

st.title("📦 Productos")

# =================================================
# Carga de datos
# =================================================
@st.cache_data
def load_data():
    df = pd.read_parquet("data/analytics/fact_sales_margin.parquet")
    df["sale_date"] = pd.to_datetime(df["sale_date"])
    return df

df = load_data()

# =================================================
# Filtro de periodo
# =================================================
st.subheader("Periodo de análisis")

max_date = df["sale_date"].max()

# Determinar periodo por defecto
if 'filter_option_products' not in st.session_state:
    st.session_state.filter_option_products = "Todo"

filter_option = st.radio(
    "Selecciona periodo",
    options=["Última semana", "Últimas 2 semanas", "Último mes", "Todo", "Personalizado"],
    index=["Última semana", "Últimas 2 semanas", "Último mes", "Todo", "Personalizado"].index(st.session_state.filter_option_products),
    horizontal=True,
    label_visibility="collapsed"
)

st.session_state.filter_option_products = filter_option

# Calcular fechas según opción
if filter_option == "Última semana":
    start_date = max_date - timedelta(days=7)
    end_date = max_date
elif filter_option == "Últimas 2 semanas":
    start_date = max_date - timedelta(days=14)
    end_date = max_date
elif filter_option == "Último mes":
    start_date = max_date - timedelta(days=30)
    end_date = max_date
elif filter_option == "Todo":
    start_date = df["sale_date"].min()
    end_date = max_date
else:  # Personalizado
    st.markdown("**Personaliza el periodo:**")
    col_custom1, col_custom2 = st.columns(2)
    
    with col_custom1:
        custom_start = st.date_input(
            "Fecha inicio",
            value=df["sale_date"].min().date(),
            min_value=df["sale_date"].min().date(),
            max_value=max_date.date(),
            key="product_start"
        )
    
    with col_custom2:
        custom_end = st.date_input(
            "Fecha fin",
            value=max_date.date(),
            min_value=df["sale_date"].min().date(),
            max_value=max_date.date(),
            key="product_end"
        )
    
    start_date = pd.to_datetime(custom_start)
    end_date = pd.to_datetime(custom_end)

# Filtrar datos por periodo
df_filtered = df[(df["sale_date"] >= start_date) & (df["sale_date"] <= end_date)]

st.caption(f"Mostrando datos del {start_date.strftime('%d/%m/%Y')} al {end_date.strftime('%d/%m/%Y')}")

st.divider()

# =================================================
# Flags de calidad
# =================================================
df_filtered["cost_valid"] = (
    df_filtered["unit_cost"].notna() &
    (df_filtered["unit_cost"] > 0) &
    (~df_filtered["cost_estimated"])
)

# =================================================
# Resumen
# =================================================
total_products = df_filtered["product_name"].nunique()
products_with_cost = df_filtered[df_filtered["cost_valid"]]["product_name"].nunique()

pct_valid = (
    products_with_cost / total_products * 100
    if total_products > 0 else 0
)

# Métricas personalizadas con HTML
st.markdown(f"""
<div style="display: flex; gap: 10px; margin-bottom: 20px;">
    <div style="flex: 1; background-color: #f0f2f6; padding: 15px; border-radius: 5px;">
        <div style="font-size: 14px; color: #31333F;">Productos vendidos</div>
        <div style="font-size: 24px; font-weight: 600; color: #31333F;">{total_products}</div>
    </div>
    <div style="flex: 1; background-color: #f0f2f6; padding: 15px; border-radius: 5px;">
        <div style="font-size: 14px; color: #31333F;">Con costo validado</div>
        <div style="font-size: 24px; font-weight: 600; color: #31333F;">{pct_valid:.1f}%</div>
    </div>
</div>
""", unsafe_allow_html=True)

st.caption("ℹ️ Nota sobre margenes: Los costos actuales se aplican a todo el periodo historico. Precision total desde octubre 2025; periodos anteriores son una aproximacion consistente.")

st.divider()

# =================================================
# Top productos por ventas
# =================================================
st.subheader("Top productos por ventas")

top_sales = (
    df_filtered
    .groupby("product_name")[["quantity", "net_amount"]]
    .sum()
    .sort_values("net_amount", ascending=False)
    .head(10)
    .reset_index()
)

# Formatear y renombrar
top_sales_display = top_sales.copy()
top_sales_display["quantity"] = top_sales_display["quantity"].apply(lambda x: f"{x:,.0f}")
top_sales_display["net_amount"] = top_sales_display["net_amount"].apply(lambda x: f"${x:,.2f}")

top_sales_display = top_sales_display.rename(columns={
    "product_name": "Producto",
    "quantity": "Cantidad vendida",
    "net_amount": "Ventas"
})

st.dataframe(
    top_sales_display,
    use_container_width=True,
    hide_index=True
)

# =================================================
# Top productos por margen (solo costo válido)
# =================================================
st.subheader("Top productos por margen")

margin_df = df_filtered[df_filtered["cost_valid"]].copy()

top_margin = (
    margin_df
    .groupby("product_name")[["net_amount", "gross_margin"]]
    .sum()
    .reset_index()
)

top_margin["margin_pct"] = (
    top_margin["gross_margin"] / top_margin["net_amount"] * 100
)

top_margin = (
    top_margin
    .sort_values("gross_margin", ascending=False)
    .head(10)
)

# Formatear y renombrar
top_margin_display = top_margin.copy()
top_margin_display["net_amount"] = top_margin_display["net_amount"].apply(lambda x: f"${x:,.2f}")
top_margin_display["gross_margin"] = top_margin_display["gross_margin"].apply(lambda x: f"${x:,.2f}")
top_margin_display["margin_pct"] = top_margin_display["margin_pct"].apply(lambda x: f"{x:.2f}%")

top_margin_display = top_margin_display.rename(columns={
    "product_name": "Producto",
    "net_amount": "Ventas",
    "gross_margin": "Margen bruto",
    "margin_pct": "(% Margen)"
})

st.dataframe(
    top_margin_display,
    use_container_width=True,
    hide_index=True
)

# =================================================
# Productos problemáticos
# =================================================
st.subheader("Productos a revisar")

# Margen negativo
neg_margin = (
    margin_df
    .groupby("product_name")[["gross_margin"]]
    .sum()
    .query("gross_margin < 0")
    .reset_index()
)

# Formatear
if not neg_margin.empty:
    neg_margin_display = neg_margin.copy()
    neg_margin_display["gross_margin"] = neg_margin_display["gross_margin"].apply(lambda x: f"${x:,.2f}")
    neg_margin_display = neg_margin_display.rename(columns={
        "product_name": "Producto",
        "gross_margin": "Margen bruto"
    })
else:
    neg_margin_display = neg_margin

# Costo pendiente
pending_cost = (
    df_filtered[~df_filtered["cost_valid"]]
    .groupby("product_name")["net_amount"]
    .sum()
    .reset_index()
)

# Formatear
if not pending_cost.empty:
    pending_cost_display = pending_cost.copy()
    pending_cost_display["net_amount"] = pending_cost_display["net_amount"].apply(lambda x: f"${x:,.2f}")
    pending_cost_display = pending_cost_display.rename(columns={
        "product_name": "Producto",
        "net_amount": "Ventas"
    })
    pending_cost_display = pending_cost_display.sort_values("Ventas", ascending=False, key=lambda x: x.str.replace('$', '').str.replace(',', '').astype(float))
else:
    pending_cost_display = pending_cost

col3, col4 = st.columns(2)

with col3:
    st.markdown("**Margen negativo**")
    if neg_margin.empty:
        st.success("Ninguno")
    else:
        st.dataframe(
            neg_margin_display,
            use_container_width=True,
            hide_index=True
        )

with col4:
    st.markdown("**Costo pendiente de validar**")
    if pending_cost.empty:
        st.success("Todos con costo válido")
    else:
        st.dataframe(
            pending_cost_display,
            use_container_width=True,
            hide_index=True
        )