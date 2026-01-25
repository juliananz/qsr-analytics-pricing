import streamlit as st
import pandas as pd
from datetime import timedelta

# =================================================
# Configuración
# =================================================
st.set_page_config(page_title="Hoy", layout="centered")
st.title("📅 Hoy / Semana")

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
# Fecha de referencia (último día con ventas)
# =================================================
today = df["sale_date"].max().normalize()

st.caption(f"Último día con ventas: {today.strftime('%d de %B de %Y')}")

# =================================================
# A. HOY
# =================================================
today_df = df[df["sale_date"] == today]

today_sales = today_df["net_amount"].sum()
today_margin = today_df["gross_margin"].sum()
today_margin_pct = (
    today_margin / today_sales * 100 if today_sales > 0 else 0
)

# Métricas personalizadas con HTML para forzar layout en móvil
st.markdown(f"""
<div style="display: flex; gap: 10px; margin-bottom: 20px;">
    <div style="flex: 1; background-color: #f0f2f6; padding: 15px; border-radius: 5px;">
        <div style="font-size: 14px; color: #31333F;">Ventas hoy</div>
        <div style="font-size: 24px; font-weight: 600; color: #31333F;">${today_sales:,.0f}</div>
    </div>
    <div style="flex: 1; background-color: #f0f2f6; padding: 15px; border-radius: 5px;">
        <div style="font-size: 14px; color: #31333F;">Margen hoy</div>
        <div style="font-size: 24px; font-weight: 600; color: #31333F;">${today_margin:,.0f}</div>
        <div style="font-size: 14px; color: #09ab3b;">{today_margin_pct:.1f}%</div>
    </div>
</div>
""", unsafe_allow_html=True)

# =================================================
# B. SEMANA ACTUAL (lunes a hoy)
# =================================================
week_start = today - timedelta(days=today.weekday())

week_df = df[
    (df["sale_date"] >= week_start) &
    (df["sale_date"] <= today)
]

week_sales = week_df["net_amount"].sum()
week_margin = week_df["gross_margin"].sum()
week_margin_pct = (
    week_margin / week_sales * 100 if week_sales > 0 else 0
)

st.divider()

# Métricas semanales personalizadas con HTML
st.markdown(f"""
<div style="display: flex; gap: 10px; margin-bottom: 20px;">
    <div style="flex: 1; background-color: #f0f2f6; padding: 15px; border-radius: 5px;">
        <div style="font-size: 14px; color: #31333F;">Ventas semana</div>
        <div style="font-size: 24px; font-weight: 600; color: #31333F;">${week_sales:,.0f}</div>
    </div>
    <div style="flex: 1; background-color: #f0f2f6; padding: 15px; border-radius: 5px;">
        <div style="font-size: 14px; color: #31333F;">Margen semana</div>
        <div style="font-size: 24px; font-weight: 600; color: #31333F;">${week_margin:,.0f}</div>
        <div style="font-size: 14px; color: #09ab3b;">{week_margin_pct:.1f}%</div>
    </div>
</div>
""", unsafe_allow_html=True)

# =================================================
# C. Top productos del día (por margen)
# =================================================
st.subheader("Productos que más aportaron hoy")

top_products = (
    today_df
    .groupby("product_name")[["net_amount", "gross_margin"]]
    .sum()
    .sort_values("gross_margin", ascending=False)
    .head(5)
    .reset_index()
)

if top_products.empty:
    st.info("No hay ventas registradas para hoy.")
else:
    top_products["margin_pct"] = (
        top_products["gross_margin"] / top_products["net_amount"] * 100
    ).round(1)
    
    # Formatear columnas para mostrar
    top_products_display = top_products.copy()
    top_products_display["net_amount"] = top_products_display["net_amount"].apply(lambda x: f"${x:,.0f}")
    top_products_display["gross_margin"] = top_products_display["gross_margin"].apply(lambda x: f"${x:,.0f}")
    top_products_display["margin_pct"] = top_products_display["margin_pct"].apply(lambda x: f"{x:.1f}%")
    
    # Renombrar columnas
    top_products_display = top_products_display.rename(columns={
        "product_name": "Producto",
        "net_amount": "Ventas",
        "gross_margin": "Margen bruto",
        "margin_pct": "(% Margen)"
    })

    st.dataframe(
        top_products_display,
        use_container_width=True,
        hide_index=True
    )

# =================================================
# D. Alertas operativas simples
# =================================================
st.subheader("Alertas")

alerts = []

# Margen diario bajo
if today_margin_pct < 40:
    alerts.append(
        f"⚠️ Margen bajo hoy ({today_margin_pct:.1f}%)."
    )

# Productos con margen negativo hoy
neg_products = top_products[top_products["gross_margin"] < 0]

if not neg_products.empty:
    alerts.append(
        "⚠️ Hay productos vendidos hoy con margen negativo."
    )

# Semana por debajo del promedio reciente
recent_weeks = (
    df[df["sale_date"] < today]
    .assign(
        week=lambda x: x["sale_date"] - pd.to_timedelta(x["sale_date"].dt.weekday, unit="D")
    )
    .groupby("week")["net_amount"]
    .sum()
    .tail(4)
)

if len(recent_weeks) >= 3:
    avg_recent = recent_weeks[:-1].mean()
    if week_sales < avg_recent * 0.9:
        alerts.append(
            "⚠️ Ventas de la semana van por debajo del promedio reciente."
        )

if not alerts:
    st.success("Todo se ve normal hoy.")
else:
    for a in alerts:
        st.write(a)