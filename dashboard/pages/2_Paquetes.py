import streamlit as st
import pandas as pd

st.set_page_config(page_title="Paquetes", layout="centered")
st.title("📦 Paquetes")

# =================================================
# Carga de datos
# =================================================
@st.cache_data
def load_data():
    df = pd.read_parquet("data/analytics/fact_sales_margin.parquet")
    df["sale_date"] = pd.to_datetime(df["sale_date"])
    return df

@st.cache_data
def load_bundle_mapping():
    mapping = pd.read_csv("data/processed_data/product_name_mapping.csv")
    # Crear diccionario: bundle_code -> raw_product_name
    bundle_dict = mapping[mapping["bundle_code"].notna()].set_index("bundle_code")["raw_product_name"].to_dict()
    return bundle_dict

df = load_data()
bundle_names = load_bundle_mapping()

# =================================================
# Filtro de periodo
# =================================================
st.subheader("Periodo de análisis")

max_date = df["sale_date"].max()

# Botones predeterminados
col_period1, col_period2, col_period3, col_period4 = st.columns(4)

if col_period1.button("Última semana"):
    start_date = max_date - pd.Timedelta(days=7)
    end_date = max_date
elif col_period2.button("Últimas 2 semanas"):
    start_date = max_date - pd.Timedelta(days=14)
    end_date = max_date
elif col_period3.button("Último mes"):
    start_date = max_date - pd.Timedelta(days=30)
    end_date = max_date
elif col_period4.button("Todo"):
    start_date = df["sale_date"].min()
    end_date = max_date
else:
    # Valores por defecto (todo el periodo)
    if 'start_date_bundles' not in st.session_state:
        start_date = df["sale_date"].min()
        end_date = max_date
    else:
        start_date = st.session_state.start_date_bundles
        end_date = st.session_state.end_date_bundles

# Guardar en session_state
st.session_state.start_date_bundles = start_date
st.session_state.end_date_bundles = end_date

# Selector personalizado
st.markdown("**O personaliza el periodo:**")
col_custom1, col_custom2 = st.columns(2)

with col_custom1:
    custom_start = st.date_input(
        "Fecha inicio",
        value=start_date.date(),
        min_value=df["sale_date"].min().date(),
        max_value=max_date.date(),
        key="bundle_start"
    )

with col_custom2:
    custom_end = st.date_input(
        "Fecha fin",
        value=end_date.date(),
        min_value=df["sale_date"].min().date(),
        max_value=max_date.date(),
        key="bundle_end"
    )

# Actualizar periodo si se personaliza
start_date = pd.to_datetime(custom_start)
end_date = pd.to_datetime(custom_end)

# Filtrar datos por periodo
df_filtered = df[(df["sale_date"] >= start_date) & (df["sale_date"] <= end_date)]

st.caption(f"Mostrando datos del {start_date.strftime('%d/%m/%Y')} al {end_date.strftime('%d/%m/%Y')}")

st.divider()

# =================================================
# Filtrar solo paquetes
# =================================================
bundles = df_filtered[df_filtered["bundle_code"].notna()].copy()

if bundles.empty:
    st.warning("No hay ventas de paquetes registradas.")
    st.stop()

# Mapear bundle_code a nombre
bundles["bundle_name"] = bundles["bundle_code"].map(bundle_names).fillna(bundles["bundle_code"])

# =================================================
# Resumen
# =================================================
total_bundle_sales = bundles["net_amount"].sum()
total_sales = df_filtered["net_amount"].sum()

bundle_share = total_bundle_sales / total_sales * 100

bundle_units = bundles["quantity"].sum()

# Métricas personalizadas con HTML
st.markdown(f"""
<div style="display: flex; gap: 10px; margin-bottom: 20px;">
    <div style="flex: 1; background-color: #f0f2f6; padding: 15px; border-radius: 5px;">
        <div style="font-size: 14px; color: #31333F;">Ventas en paquetes</div>
        <div style="font-size: 24px; font-weight: 600; color: #31333F;">${total_bundle_sales:,.0f}</div>
    </div>
    <div style="flex: 1; background-color: #f0f2f6; padding: 15px; border-radius: 5px;">
        <div style="font-size: 14px; color: #31333F;">Participación paquetes</div>
        <div style="font-size: 24px; font-weight: 600; color: #31333F;">{bundle_share:.1f}%</div>
    </div>
</div>
""", unsafe_allow_html=True)

st.caption(f"Unidades de paquetes vendidas: {bundle_units:,}")

st.divider()

# =================================================
# Top paquetes por ventas
# =================================================
st.subheader("Top paquetes por ventas")

top_sales = (
    bundles
    .groupby("bundle_name")[["quantity", "net_amount"]]
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
    "bundle_name": "Nombre paquete",
    "quantity": "Cantidad vendida",
    "net_amount": "Ventas"
})

st.dataframe(
    top_sales_display,
    use_container_width=True,
    hide_index=True
)

# =================================================
# Top paquetes por margen
# =================================================
st.subheader("Top paquetes por margen")

margin_df = (
    bundles
    .groupby("bundle_name")[["net_amount", "gross_margin"]]
    .sum()
    .reset_index()
)

margin_df["margin_pct"] = (
    margin_df["gross_margin"] / margin_df["net_amount"] * 100
)

top_margin = (
    margin_df
    .sort_values("gross_margin", ascending=False)
    .head(10)
)

# Formatear y renombrar
top_margin_display = top_margin.copy()
top_margin_display["net_amount"] = top_margin_display["net_amount"].apply(lambda x: f"${x:,.2f}")
top_margin_display["gross_margin"] = top_margin_display["gross_margin"].apply(lambda x: f"${x:,.2f}")
top_margin_display["margin_pct"] = top_margin_display["margin_pct"].apply(lambda x: f"{x:.2f}%")

top_margin_display = top_margin_display.rename(columns={
    "bundle_name": "Nombre paquete",
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
# Paquetes a revisar
# =================================================
st.subheader("Paquetes a revisar")

low_margin = margin_df.query("margin_pct < 40").sort_values("margin_pct")

if low_margin.empty:
    st.success("Todos los paquetes tienen margen saludable.")
else:
    # Formatear y renombrar
    low_margin_display = low_margin.copy()
    low_margin_display["net_amount"] = low_margin_display["net_amount"].apply(lambda x: f"${x:,.2f}")
    low_margin_display["gross_margin"] = low_margin_display["gross_margin"].apply(lambda x: f"${x:,.2f}")
    low_margin_display["margin_pct"] = low_margin_display["margin_pct"].apply(lambda x: f"{x:.2f}%")
    
    low_margin_display = low_margin_display.rename(columns={
        "bundle_name": "Nombre paquete",
        "net_amount": "Ventas",
        "gross_margin": "Margen bruto",
        "margin_pct": "(% Margen)"
    })
    
    st.dataframe(
        low_margin_display,
        use_container_width=True,
        hide_index=True
    )