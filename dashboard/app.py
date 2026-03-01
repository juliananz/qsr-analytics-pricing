import os
from datetime import date

import streamlit as st
import pandas as pd

import demo

_ANALYTICS_DIR = (
    "data/demo" if os.getenv("DEMO_MODE", "").lower() == "true"
    else "data/analytics"
)

# =================================================
# Configuracion de pagina (debe ser la primera llamada)
# =================================================
st.set_page_config(
    page_title="Hoy - QSR Analytics",
    page_icon="\U0001f354",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# =================================================
# Helpers de fecha en espanol (sin dependencia de locale)
# =================================================
DIAS = {
    0: "Lunes",
    1: "Martes",
    2: "Miercoles",
    3: "Jueves",
    4: "Viernes",
    5: "Sabado",
    6: "Domingo",
}
MESES = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}


def formato_fecha(dt):
    return f"{DIAS[dt.weekday()]} {dt.day} de {MESES[dt.month]}, {dt.year}"


def formato_moneda(valor):
    if valor >= 0:
        return f"${valor:,.0f}"
    return f"-${abs(valor):,.0f}"


# =================================================
# Carga de datos (cacheada)
# =================================================
@st.cache_data
def load_cortes():
    try:
        df = pd.read_csv("data/raw_data/cortes_validated.csv")
        df["fecha"] = pd.to_datetime(df["fecha"])
        return df
    except FileNotFoundError:
        return pd.DataFrame()


@st.cache_data
def load_gastos():
    try:
        df = pd.read_csv("data/raw_data/gastos_validated.csv")
        df["fecha"] = pd.to_datetime(df["fecha"])
        return df
    except FileNotFoundError:
        return pd.DataFrame(
            columns=["fecha", "descripcion", "categoria", "monto"]
        )


@st.cache_data
def load_margins():
    try:
        df = pd.read_parquet(f"{_ANALYTICS_DIR}/fact_sales_margin.parquet")
        df["sale_date"] = pd.to_datetime(df["sale_date"])
        return df
    except FileNotFoundError:
        return pd.DataFrame()


@st.cache_data
def load_recipes():
    try:
        return pd.read_csv("data/processed_data/recipe_items.csv")
    except FileNotFoundError:
        return pd.DataFrame()


@st.cache_data
def load_bundle_components():
    try:
        return pd.read_csv("data/processed_data/bundle_components.csv")
    except FileNotFoundError:
        return pd.DataFrame()


@st.cache_data
def load_ingredient_costs():
    try:
        return pd.read_csv("data/processed_data/dim_input_costs.csv")
    except FileNotFoundError:
        return pd.DataFrame()


@st.cache_data
def load_sales_raw():
    try:
        df = pd.read_parquet(
            "data/analytics/fact_sales_raw.parquet",
            columns=["sale_date", "orden"],
        )
    except FileNotFoundError:
        return pd.DataFrame()
    except KeyError:
        # "orden" column missing from parquet schema
        return pd.DataFrame()
    df["sale_date"] = pd.to_datetime(df["sale_date"]).dt.normalize()
    # Clean orden: drop nulls first, then cast, strip, drop blanks
    df = df.dropna(subset=["orden"])
    df["orden"] = df["orden"].astype(str).str.strip()
    df = df[~df["orden"].isin(["", "nan", "None"])]
    return df


cortes_df = load_cortes()
gastos_df = load_gastos()
margins_df = load_margins()

# Apply demo anonymization (no-op when DEMO_MODE is not set)
cortes_df = demo.apply_cortes(cortes_df)
gastos_df = demo.apply_gastos(gastos_df)
margins_df = demo.apply_margins(margins_df)

if not margins_df.empty:
    _last_date = margins_df["sale_date"].max().date()
    _days_old = (date.today() - _last_date).days
    if _days_old > 1:
        st.warning(
            f"⚠️ Data is {_days_old} day(s) old. "
            f"Last updated: {_last_date}. Check the pipeline."
        )

sales_raw_df = load_sales_raw()
recipes_df = load_recipes()
bundles_df = load_bundle_components()
ingredients_df = load_ingredient_costs()

# =================================================
# Estado vacio: sin cortes
# =================================================
st.title("Hoy")

if demo.is_demo_mode():
    demo.banner()

if margins_df.empty:
    st.info(
        "No hay datos de ventas disponibles. "
        "Cuando se procese el primer archivo POS, "
        "aqui veras el resumen del dia."
    )
    st.stop()

# =================================================
# Fecha de referencia (ultimo dia con datos POS)
# =================================================
ref_date = margins_df["sale_date"].max().normalize()
st.caption(formato_fecha(ref_date))

_today_cortes = cortes_df[cortes_df["fecha"] == ref_date] if not cortes_df.empty else pd.DataFrame()
today_row = _today_cortes.iloc[0] if not _today_cortes.empty else None
if today_row is None:
    st.caption("Corte de caja aun no registrado para este dia.")

# =================================================
# Seccion 1: Ventas del dia + Ganancia esperada
# =================================================
ventas_efectivo = today_row["ventas_efectivo"] if today_row is not None else 0
ventas_tarjeta = today_row["ventas_tarjeta"] if today_row is not None else 0
ventas_app = today_row["ventas_app"] if today_row is not None else 0
ventas_total = ventas_efectivo + ventas_tarjeta + ventas_app

if not margins_df.empty:
    today_margins = margins_df[margins_df["sale_date"] == ref_date]
    ganancia_bruta = today_margins["gross_margin"].sum()
else:
    ganancia_bruta = 0

# IVA: prepared food in Mexico includes 16% IVA in the price
iva_estimado = ventas_total * 16 / 116
ganancia_esperada = ganancia_bruta - iva_estimado

color_ganancia = "#09ab3b" if ganancia_esperada >= 0 else "#ff4b4b"

st.markdown(
    f"""
<div style="display: flex; gap: 8px; margin-bottom: 16px;">
    <div style="flex: 1; background-color: #f0f2f6; padding: 20px;
                border-radius: 8px; text-align: center;">
        <div style="font-size: 14px; color: #555;">Ventas del dia</div>
        <div style="font-size: 32px; font-weight: 700; color: #31333F;">
            {formato_moneda(ventas_total)}
        </div>
    </div>
    <div style="flex: 1; background-color: #f0f2f6; padding: 20px;
                border-radius: 8px; text-align: center;">
        <div style="font-size: 14px; color: #555;">IVA estimado (16%)</div>
        <div style="font-size: 32px; font-weight: 700; color: #ff8c00;">
            {formato_moneda(iva_estimado)}
        </div>
    </div>
    <div style="flex: 1; background-color: #f0f2f6; padding: 20px;
                border-radius: 8px; text-align: center;">
        <div style="font-size: 14px; color: #555;">Ganancia esperada</div>
        <div style="font-size: 32px; font-weight: 700; color: {color_ganancia};">
            {formato_moneda(ganancia_esperada)}
        </div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

# =================================================
# Seccion 1b: Clientes y ticket promedio
# =================================================
if sales_raw_df.empty:
    st.caption("Metricas de clientes no disponibles (sin datos de ordenes).")
else:
    today_orders = sales_raw_df[sales_raw_df["sale_date"] == ref_date]
    num_customers = today_orders["orden"].nunique()
    ticket_promedio = ventas_total / num_customers if num_customers > 0 else 0

    st.markdown(
        f"""
<div style="display: flex; gap: 8px; margin-bottom: 16px;">
    <div style="flex: 1; background-color: #f0f2f6; padding: 12px;
                border-radius: 8px; text-align: center;">
        <div style="font-size: 13px; color: #555;">Clientes</div>
        <div style="font-size: 20px; font-weight: 600; color: #31333F;">
            {num_customers:,}
        </div>
    </div>
    <div style="flex: 1; background-color: #f0f2f6; padding: 12px;
                border-radius: 8px; text-align: center;">
        <div style="font-size: 13px; color: #555;">Ticket promedio</div>
        <div style="font-size: 20px; font-weight: 600; color: #31333F;">
            {formato_moneda(ticket_promedio)}
        </div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

# =================================================
# Seccion 2: Desglose por forma de pago
# =================================================
st.markdown(
    f"""
<div style="display: flex; gap: 8px; margin-bottom: 20px;">
    <div style="flex: 1; background-color: #f0f2f6; padding: 12px;
                border-radius: 8px; text-align: center;">
        <div style="font-size: 13px; color: #555;">Efectivo</div>
        <div style="font-size: 20px; font-weight: 600; color: #31333F;">
            {formato_moneda(ventas_efectivo)}
        </div>
    </div>
    <div style="flex: 1; background-color: #f0f2f6; padding: 12px;
                border-radius: 8px; text-align: center;">
        <div style="font-size: 13px; color: #555;">Tarjeta</div>
        <div style="font-size: 20px; font-weight: 600; color: #31333F;">
            {formato_moneda(ventas_tarjeta)}
        </div>
    </div>
    <div style="flex: 1; background-color: #f0f2f6; padding: 12px;
                border-radius: 8px; text-align: center;">
        <div style="font-size: 13px; color: #555;">Apps</div>
        <div style="font-size: 20px; font-weight: 600; color: #31333F;">
            {formato_moneda(ventas_app)}
        </div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

# =================================================
# Seccion 2b: Cuadre de caja (sistema vs calculado)
# =================================================
if today_row is not None:
    ventas_sistema = today_row["ventas_sistema"]
    ventas_calculadas = (
        ventas_efectivo + ventas_tarjeta + ventas_app + today_row["gastos_caja"]
    )
    diferencia_cuadre = ventas_calculadas - ventas_sistema
    color_dif = "#09ab3b" if diferencia_cuadre == 0 else "#ff4b4b"

    st.markdown(
        f"""
<div style="display: flex; gap: 8px; margin-bottom: 20px;">
    <div style="flex: 1; background-color: #f0f2f6; padding: 12px;
                border-radius: 8px; text-align: center;">
        <div style="font-size: 13px; color: #555;">Ventas sistema</div>
        <div style="font-size: 18px; font-weight: 600; color: #31333F;">
            {formato_moneda(ventas_sistema)}
        </div>
    </div>
    <div style="flex: 1; background-color: #f0f2f6; padding: 12px;
                border-radius: 8px; text-align: center;">
        <div style="font-size: 13px; color: #555;">Ventas calculadas</div>
        <div style="font-size: 18px; font-weight: 600; color: #31333F;">
            {formato_moneda(ventas_calculadas)}
        </div>
    </div>
    <div style="flex: 1; background-color: #f0f2f6; padding: 12px;
                border-radius: 8px; text-align: center;">
        <div style="font-size: 13px; color: #555;">Diferencia</div>
        <div style="font-size: 18px; font-weight: 600; color: {color_dif};">
            {formato_moneda(diferencia_cuadre)}
        </div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

# =================================================
# Seccion 2c: KPIs de carnes y papas
# =================================================
if not margins_df.empty and not recipes_df.empty and not ingredients_df.empty:
    # Identify meat ingredients
    meat_ingredients = set(
        ingredients_df[ingredients_df["ingredient_group"] == "Carne"]["ingredient_name"]
    )

    # Build product_code → meat_units lookup
    meat_per_product = (
        recipes_df[recipes_df["ingredient_name"].isin(meat_ingredients)]
        .groupby("product_code")["quantity"]
        .sum()
        .to_dict()
    )

    # Build bundle_code → meat_units and fries_units lookups
    meat_per_bundle = {}
    fries_per_bundle = {}
    if not bundles_df.empty:
        relevant = bundles_df[bundles_df["component_type"].isin(("product", "side"))].copy()
        relevant["meat_units"] = relevant["component_code"].map(meat_per_product).fillna(0) * relevant["quantity"]
        relevant["fries_units"] = relevant["quantity"].where(relevant["component_code"] == "fries_full", 0)
        meat_per_bundle = relevant.groupby("bundle_code")["meat_units"].sum().to_dict()
        fries_per_bundle = relevant.groupby("bundle_code")["fries_units"].sum().to_dict()

    # Calculate today's meat units and fries orders
    today_sales = margins_df[margins_df["sale_date"] == ref_date].copy()
    has_bundle = today_sales["bundle_code"].notna()
    today_sales["meat_units"] = (
        today_sales["bundle_code"].map(meat_per_bundle).fillna(0) * today_sales["quantity"]
    ).where(has_bundle, today_sales["product_code"].map(meat_per_product).fillna(0) * today_sales["quantity"])
    today_sales["fries_units"] = (
        today_sales["bundle_code"].map(fries_per_bundle).fillna(0) * today_sales["quantity"]
    ).where(has_bundle, today_sales["quantity"].where(today_sales["product_code"] == "fries_full", 0))
    total_meat = today_sales["meat_units"].sum()
    total_fries = today_sales["fries_units"].sum()

    venta_por_carne = ventas_total / total_meat if total_meat > 0 else 0
    ratio_carne_papas = total_meat / total_fries if total_fries > 0 else 0

    st.markdown(
        f"""
<div style="display: flex; gap: 8px; margin-bottom: 20px;">
    <div style="flex: 1; background-color: #f0f2f6; padding: 12px;
                border-radius: 8px; text-align: center;">
        <div style="font-size: 13px; color: #555;">Carnes vendidas</div>
        <div style="font-size: 18px; font-weight: 600; color: #31333F;">
            {total_meat:,.0f}
        </div>
    </div>
    <div style="flex: 1; background-color: #f0f2f6; padding: 12px;
                border-radius: 8px; text-align: center;">
        <div style="font-size: 13px; color: #555;">Venta / carne</div>
        <div style="font-size: 18px; font-weight: 600; color: #31333F;">
            {formato_moneda(venta_por_carne)}
        </div>
    </div>
    <div style="flex: 1; background-color: #f0f2f6; padding: 12px;
                border-radius: 8px; text-align: center;">
        <div style="font-size: 13px; color: #555;">Carnes / Papas</div>
        <div style="font-size: 18px; font-weight: 600; color: #31333F;">
            {ratio_carne_papas:.2f}
        </div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

# =================================================
# Seccion 3: Gastos del dia (total)
# =================================================
st.divider()

today_gastos = gastos_df[gastos_df["fecha"] == ref_date]
gastos_total = today_gastos["monto"].sum() if not today_gastos.empty else 0

st.markdown(
    f"""
<div style="background-color: #f0f2f6; padding: 20px; border-radius: 8px;
            text-align: center; margin-bottom: 12px;">
    <div style="font-size: 14px; color: #555;">Gastos del dia</div>
    <div style="font-size: 28px; font-weight: 700; color: #31333F;">
        {formato_moneda(gastos_total)}
    </div>
</div>
""",
    unsafe_allow_html=True,
)

# =================================================
# Seccion 4: Gastos detalle (toggle categoria / individual)
# =================================================
if today_gastos.empty:
    st.caption("Sin gastos registrados para este dia.")
else:
    vista_gastos = st.radio(
        "Ver gastos:",
        ["Por categoria", "Individual"],
        horizontal=True,
        key="vista_gastos",
    )

    if vista_gastos == "Por categoria":
        cat_breakdown = (
            today_gastos.groupby("categoria")["monto"]
            .sum()
            .sort_values(ascending=False)
        )

        rows_html = ""
        for categoria, monto in cat_breakdown.items():
            rows_html += f"""
    <div style="display: flex; justify-content: space-between;
                padding: 8px 12px; border-bottom: 1px solid #e0e0e0;">
        <span style="font-size: 14px; color: #31333F;">{categoria}</span>
        <span style="font-size: 14px; font-weight: 600; color: #31333F;">
            {formato_moneda(monto)}
        </span>
    </div>"""

        st.markdown(
            f'<div style="margin-bottom: 20px;">{rows_html}\n</div>',
            unsafe_allow_html=True,
        )
    else:
        individual = (
            today_gastos[["descripcion", "categoria", "monto"]]
            .sort_values("monto", ascending=False)
        )

        rows_html = "".join(
            f"""
    <div style="display: flex; justify-content: space-between; align-items: baseline;
                padding: 8px 12px; border-bottom: 1px solid #e0e0e0;">
        <div>
            <span style="font-size: 14px; color: #31333F;">{desc}</span>
            <span style="font-size: 12px; color: #888; margin-left: 6px;">{cat}</span>
        </div>
        <span style="font-size: 14px; font-weight: 600; color: #31333F; white-space: nowrap;">
            {formato_moneda(monto)}
        </span>
    </div>"""
            for desc, cat, monto in zip(
                individual["descripcion"], individual["categoria"], individual["monto"]
            )
        )

        st.markdown(
            f'<div style="margin-bottom: 20px;">{rows_html}\n</div>',
            unsafe_allow_html=True,
        )

# =================================================
# Seccion 5: Resultado del dia
# =================================================
st.divider()

resultado = ventas_total - gastos_total
color_resultado = "#09ab3b" if resultado >= 0 else "#ff4b4b"

st.markdown(
    f"""
<div style="background-color: #f0f2f6; padding: 20px; border-radius: 8px;
            text-align: center; margin-bottom: 16px;">
    <div style="font-size: 14px; color: #555;">Resultado del dia</div>
    <div style="font-size: 32px; font-weight: 700; color: {color_resultado};">
        {formato_moneda(resultado)}
    </div>
    <div style="font-size: 13px; color: #888;">Ventas menos gastos</div>
</div>
""",
    unsafe_allow_html=True,
)

# =================================================
# Seccion 6: Esta semana (lunes a fecha de referencia)
# =================================================
st.divider()
st.subheader("Esta semana")

week_start = ref_date - pd.Timedelta(days=ref_date.weekday())
days_in_week = (ref_date - week_start).days + 1

st.caption(
    f"{DIAS[week_start.weekday()]} {week_start.day} a "
    f"{DIAS[ref_date.weekday()].lower()} {ref_date.day} "
    f"({days_in_week} {'dia' if days_in_week == 1 else 'dias'})"
)

week_cortes = cortes_df[
    (cortes_df["fecha"] >= week_start) & (cortes_df["fecha"] <= ref_date)
]
week_ventas = (
    week_cortes["ventas_efectivo"]
    + week_cortes["ventas_tarjeta"]
    + week_cortes["ventas_app"]
).sum()

week_gastos_df = gastos_df[
    (gastos_df["fecha"] >= week_start) & (gastos_df["fecha"] <= ref_date)
]

week_iva = week_ventas * 16 / 116

if not margins_df.empty:
    week_margins = margins_df[
        (margins_df["sale_date"] >= week_start) & (margins_df["sale_date"] <= ref_date)
    ]
    week_ganancia_bruta = week_margins["gross_margin"].sum()
else:
    week_ganancia_bruta = 0

week_ganancia = week_ganancia_bruta - week_iva
color_week_ganancia = "#09ab3b" if week_ganancia >= 0 else "#ff4b4b"

st.markdown(
    f"""
<div style="display: flex; gap: 8px; margin-bottom: 8px;">
    <div style="flex: 1; background-color: #f0f2f6; padding: 12px;
                border-radius: 8px; text-align: center;">
        <div style="font-size: 13px; color: #555;">Ventas</div>
        <div style="font-size: 20px; font-weight: 600; color: #31333F;">
            {formato_moneda(week_ventas)}
        </div>
    </div>
    <div style="flex: 1; background-color: #f0f2f6; padding: 12px;
                border-radius: 8px; text-align: center;">
        <div style="font-size: 13px; color: #555;">IVA estimado</div>
        <div style="font-size: 20px; font-weight: 600; color: #ff8c00;">
            {formato_moneda(week_iva)}
        </div>
    </div>
    <div style="flex: 1; background-color: #f0f2f6; padding: 12px;
                border-radius: 8px; text-align: center;">
        <div style="font-size: 13px; color: #555;">Ganancia esperada</div>
        <div style="font-size: 20px; font-weight: 600; color: {color_week_ganancia};">
            {formato_moneda(week_ganancia)}
        </div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

if not sales_raw_df.empty:
    week_orders = sales_raw_df[
        (sales_raw_df["sale_date"] >= week_start)
        & (sales_raw_df["sale_date"] <= ref_date)
    ]
    week_customers = week_orders.groupby("sale_date")["orden"].nunique().sum()
    week_ticket = week_ventas / week_customers if week_customers > 0 else 0

    st.markdown(
        f"""
<div style="display: flex; gap: 8px; margin-bottom: 8px;">
    <div style="flex: 1; background-color: #f0f2f6; padding: 12px;
                border-radius: 8px; text-align: center;">
        <div style="font-size: 13px; color: #555;">Clientes</div>
        <div style="font-size: 18px; font-weight: 600; color: #31333F;">
            {week_customers:,}
        </div>
    </div>
    <div style="flex: 1; background-color: #f0f2f6; padding: 12px;
                border-radius: 8px; text-align: center;">
        <div style="font-size: 13px; color: #555;">Ticket promedio</div>
        <div style="font-size: 18px; font-weight: 600; color: #31333F;">
            {formato_moneda(week_ticket)}
        </div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

week_gastos = week_gastos_df["monto"].sum() if not week_gastos_df.empty else 0
week_resultado = week_ventas - week_gastos
color_week = "#09ab3b" if week_resultado >= 0 else "#ff4b4b"

st.markdown(
    f"""
<div style="display: flex; gap: 8px; margin-bottom: 8px;">
    <div style="flex: 1; background-color: #f0f2f6; padding: 12px;
                border-radius: 8px; text-align: center;">
        <div style="font-size: 13px; color: #555;">Gastos</div>
        <div style="font-size: 20px; font-weight: 600; color: #31333F;">
            {formato_moneda(week_gastos)}
        </div>
    </div>
    <div style="flex: 1; background-color: #f0f2f6; padding: 12px;
                border-radius: 8px; text-align: center;">
        <div style="font-size: 13px; color: #555;">Resultado</div>
        <div style="font-size: 20px; font-weight: 600; color: {color_week};">
            {formato_moneda(week_resultado)}
        </div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

# Weekly meat & fries KPIs
if not margins_df.empty and not recipes_df.empty and not ingredients_df.empty:
    week_sales = margins_df[
        (margins_df["sale_date"] >= week_start) & (margins_df["sale_date"] <= ref_date)
    ]
    week_sales = week_sales.copy()
    has_bundle_w = week_sales["bundle_code"].notna()
    week_sales["meat_units"] = (
        week_sales["bundle_code"].map(meat_per_bundle).fillna(0) * week_sales["quantity"]
    ).where(has_bundle_w, week_sales["product_code"].map(meat_per_product).fillna(0) * week_sales["quantity"])
    week_sales["fries_units"] = (
        week_sales["bundle_code"].map(fries_per_bundle).fillna(0) * week_sales["quantity"]
    ).where(has_bundle_w, week_sales["quantity"].where(week_sales["product_code"] == "fries_full", 0))
    week_meat = week_sales["meat_units"].sum()
    week_fries = week_sales["fries_units"].sum()

    week_venta_por_carne = week_ventas / week_meat if week_meat > 0 else 0
    week_ratio_carne_papas = week_meat / week_fries if week_fries > 0 else 0

    st.markdown(
        f"""
<div style="display: flex; gap: 8px; margin-bottom: 20px;">
    <div style="flex: 1; background-color: #f0f2f6; padding: 12px;
                border-radius: 8px; text-align: center;">
        <div style="font-size: 13px; color: #555;">Carnes vendidas</div>
        <div style="font-size: 18px; font-weight: 600; color: #31333F;">
            {week_meat:,.0f}
        </div>
    </div>
    <div style="flex: 1; background-color: #f0f2f6; padding: 12px;
                border-radius: 8px; text-align: center;">
        <div style="font-size: 13px; color: #555;">Venta / carne</div>
        <div style="font-size: 18px; font-weight: 600; color: #31333F;">
            {formato_moneda(week_venta_por_carne)}
        </div>
    </div>
    <div style="flex: 1; background-color: #f0f2f6; padding: 12px;
                border-radius: 8px; text-align: center;">
        <div style="font-size: 13px; color: #555;">Carnes / Papas</div>
        <div style="font-size: 18px; font-weight: 600; color: #31333F;">
            {week_ratio_carne_papas:.2f}
        </div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

# =================================================
# Sidebar: POS upload + logout
# =================================================
with st.sidebar:
    st.subheader("Subir POS")
    uploaded = st.file_uploader("Archivo de comandas (.xlsx)", type="xlsx")
    if uploaded is not None and st.button("Procesar"):
        import requests
        import base64

        token = st.secrets["github"]["token"]
        repo = st.secrets["github"]["repo"]
        path = "data/raw_data/comandas.xlsx"
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }

        # Check if file exists (need sha to update)
        existing = requests.get(url, headers=headers)
        sha = existing.json().get("sha") if existing.status_code == 200 else None

        payload = {
            "message": "chore: upload POS comandas",
            "content": base64.b64encode(uploaded.read()).decode(),
        }
        if sha:
            payload["sha"] = sha

        resp = requests.put(url, json=payload, headers=headers)
        if resp.status_code in (200, 201):
            st.success("Archivo subido. El pipeline se ejecutara en ~2 min.")
        else:
            st.error(f"Error al subir: {resp.status_code}")

