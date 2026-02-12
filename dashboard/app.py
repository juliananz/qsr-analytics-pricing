import streamlit as st
import pandas as pd

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
        df = pd.read_parquet("data/analytics/fact_sales_margin.parquet")
        df["sale_date"] = pd.to_datetime(df["sale_date"])
        return df
    except FileNotFoundError:
        return pd.DataFrame()


cortes_df = load_cortes()
gastos_df = load_gastos()
margins_df = load_margins()

# =================================================
# Estado vacio: sin cortes
# =================================================
st.title("Hoy")

if cortes_df.empty:
    st.info(
        "No hay cortes registrados. "
        "Cuando se registre el primer corte de caja, "
        "aqui veras el resumen del dia."
    )
    st.stop()

# =================================================
# Fecha de referencia (ultimo dia con corte)
# =================================================
ref_date = cortes_df["fecha"].max().normalize()
st.caption(formato_fecha(ref_date))

today_row = cortes_df[cortes_df["fecha"] == ref_date].iloc[0]

# =================================================
# Seccion 1: Ventas del dia + Ganancia esperada
# =================================================
ventas_efectivo = today_row["ventas_efectivo"]
ventas_tarjeta = today_row["ventas_tarjeta"]
ventas_app = today_row["ventas_app"]
ventas_total = ventas_efectivo + ventas_tarjeta + ventas_app

if not margins_df.empty:
    today_margins = margins_df[margins_df["sale_date"] == ref_date]
    ganancia_esperada = today_margins["gross_margin"].sum()
else:
    ganancia_esperada = 0

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

        rows_html = ""
        for _, row in individual.iterrows():
            rows_html += f"""
    <div style="display: flex; justify-content: space-between; align-items: baseline;
                padding: 8px 12px; border-bottom: 1px solid #e0e0e0;">
        <div>
            <span style="font-size: 14px; color: #31333F;">{row['descripcion']}</span>
            <span style="font-size: 12px; color: #888; margin-left: 6px;">{row['categoria']}</span>
        </div>
        <span style="font-size: 14px; font-weight: 600; color: #31333F; white-space: nowrap;">
            {formato_moneda(row['monto'])}
        </span>
    </div>"""

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
week_gastos = week_gastos_df["monto"].sum() if not week_gastos_df.empty else 0

week_resultado = week_ventas - week_gastos
color_week = "#09ab3b" if week_resultado >= 0 else "#ff4b4b"

st.markdown(
    f"""
<div style="display: flex; gap: 8px; margin-bottom: 20px;">
    <div style="flex: 1; background-color: #f0f2f6; padding: 12px;
                border-radius: 8px; text-align: center;">
        <div style="font-size: 13px; color: #555;">Ventas</div>
        <div style="font-size: 20px; font-weight: 600; color: #31333F;">
            {formato_moneda(week_ventas)}
        </div>
    </div>
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

