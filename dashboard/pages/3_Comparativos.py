import streamlit as st
import pandas as pd
from datetime import timedelta
import plotly.graph_objects as go

import demo

# =================================================
# Configuración general
# =================================================
st.set_page_config(
    page_title="Comparativos",
    layout="centered"
)


st.title("📊 Comparativos")

if demo.is_demo_mode():
    demo.banner()

# =================================================
# Carga de datos
# =================================================
@st.cache_data
def load_data():
    df = pd.read_parquet("data/analytics/fact_sales_margin.parquet")
    df["sale_date"] = pd.to_datetime(df["sale_date"])
    return df

df = load_data()
df = demo.apply_margins(df)

# =================================================
# Fecha de corte (último día con ventas)
# =================================================
last_date = df["sale_date"].max()

cutoff = st.date_input(
    "Fecha de corte (último día con ventas)",
    value=last_date.date(),
    max_value=last_date.date()
)

cutoff = pd.to_datetime(cutoff)
df = df[df["sale_date"] <= cutoff]
cutoff_doy = cutoff.timetuple().tm_yday

current_year = cutoff.year
current_month = cutoff.month
current_month_name = cutoff.strftime("%B").capitalize()

# Preparar datos base
df["year"] = df["sale_date"].dt.year
df["day_of_year"] = df["sale_date"].dt.dayofyear

# Años completos (excluye el actual)
completed_years = sorted(df["year"].unique())
completed_years = [y for y in completed_years if y < current_year]

# Últimos 2 años completos
last_two_years = completed_years[-2:] if len(completed_years) >= 2 else completed_years

# =================================================
# A. Semana actual vs semana pasada (barras lado a lado)
# =================================================

st.subheader("Esta semana vs semana pasada")

# Calcular inicio de semana actual (lunes)
days_since_monday = cutoff.weekday()
week_start = cutoff - timedelta(days=days_since_monday)

# Definir semana actual (solo hasta el día de corte)
current_week = df[
    (df["sale_date"] >= week_start) &
    (df["sale_date"] <= cutoff)
].copy()
current_week["weekday"] = current_week["sale_date"].dt.weekday

# Definir semana pasada (solo hasta el mismo día de la semana)
prev_week_start = week_start - timedelta(days=7)
prev_week_end = prev_week_start + timedelta(days=days_since_monday)

prev_week = df[
    (df["sale_date"] >= prev_week_start) &
    (df["sale_date"] <= prev_week_end)
].copy()
prev_week["weekday"] = prev_week["sale_date"].dt.weekday

week_compare = pd.DataFrame({
    "Semana pasada": prev_week.groupby("weekday")["net_amount"].sum(),
    "Esta semana": current_week.groupby("weekday")["net_amount"].sum()
}).fillna(0)

# Mapear números a nombres de días
day_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
week_compare.index = week_compare.index.map(lambda x: day_names[x])

fig = go.Figure()

fig.add_bar(
    x=week_compare.index,
    y=week_compare["Semana pasada"],
    name="Semana pasada",
    hovertemplate="<b>%{x}</b><br>$%{y:,.0f}<extra></extra>"
)

fig.add_bar(
    x=week_compare.index,
    y=week_compare["Esta semana"],
    name="Esta semana",
    hovertemplate="<b>%{x}</b><br>$%{y:,.0f}<extra></extra>"
)

fig.update_layout(
    barmode="group",
    xaxis_title="Día",
    yaxis_title="Ventas",
    yaxis_tickformat="$,.0f",
    legend_title="Periodo",
    height=350
)

st.plotly_chart(fig, width="stretch")

# -----------------------------
# Interpretación automática
# -----------------------------
current_total = week_compare["Esta semana"].sum()
prev_total = week_compare["Semana pasada"].sum()

# Nombres de días en español
weekday_names = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
current_weekday_name = weekday_names[cutoff.weekday()]

st.info(f"Hasta el {current_weekday_name} de la semana pasada había ventas de \${prev_total:,.0f}, esta semana llevas \${current_total:,.0f}")

# =================================================
# B. Mes actual vs mismo mes años anteriores
# =================================================

# Nombres de meses en español
month_names = {
    1: ("enero", "eneros"), 2: ("febrero", "febreros"), 3: ("marzo", "marzos"),
    4: ("abril", "abriles"), 5: ("mayo", "mayos"), 6: ("junio", "junios"),
    7: ("julio", "julios"), 8: ("agosto", "agostos"), 9: ("septiembre", "septiembres"),
    10: ("octubre", "octubres"), 11: ("noviembre", "noviembres"), 12: ("diciembre", "diciembres")
}

month_singular, month_plural = month_names[current_month]

st.subheader(f"Este {month_singular} vs {month_plural} anteriores")

month_df = df[df["sale_date"].dt.month == current_month].copy()
month_df["day"] = month_df["sale_date"].dt.day

month_acc = (
    month_df.groupby(["year", "day"])["net_amount"]
    .sum()
    .groupby(level=0)
    .cumsum()
    .reset_index()
)

avg_years = [y for y in completed_years if y != 2022]
avg_month = (
    month_acc[month_acc["year"].isin(avg_years)]
    .groupby("day")["net_amount"]
    .mean()
    .reset_index()
)
avg_month["year"] = "Promedio histórico"

plot_month = pd.concat([
    month_acc[month_acc["year"].isin(last_two_years + [current_year])],
    avg_month
])

pivot_month = plot_month.pivot(
    index="day",
    columns="year",
    values="net_amount"
)

if pivot_month.empty:
    st.warning("No hay datos suficientes para mostrar el comparativo mensual.")
else:
    fig_month = go.Figure()
    for col in pivot_month.columns:
        dash = "dash" if col == "Promedio histórico" else None
        fig_month.add_trace(go.Scatter(
            x=pivot_month.index,
            y=pivot_month[col],
            name=str(col),
            mode="lines",
            line=dict(dash=dash),
            hovertemplate="<b>%{x}</b> - %{meta}<br>$%{y:,.0f}<extra></extra>",
            meta=[str(col)] * len(pivot_month),
        ))
    fig_month.update_layout(
        xaxis_title="Día del mes",
        yaxis_title="Ventas acumuladas",
        yaxis_tickformat="$,.0f",
        height=350,
        legend_title="Año",
    )
    st.plotly_chart(fig_month, use_container_width=True)

# -----------------------------
# Bullets numéricos mensuales
# -----------------------------
st.markdown(f"### Este {month_singular} vs {month_plural} anteriores")

def month_total(year):
    return df[
        (df["year"] == year) &
        (df["sale_date"].dt.month == current_month) &
        (df["sale_date"].dt.day <= cutoff.day)
    ]["net_amount"].sum()

cols_month = st.columns(3)

if len(last_two_years) == 2:
    cols_month[0].metric(
        f"{last_two_years[0]}",
        f"${month_total(last_two_years[0]):,.0f}"
    )
    cols_month[1].metric(
        f"{last_two_years[1]}",
        f"${month_total(last_two_years[1]):,.0f}"
    )

cols_month[2].metric(
    f"{current_year}",
    f"${month_total(current_year):,.0f}"
)

# =================================================
# C. Ventas acumuladas YTD (gráfica + bullets)
# =================================================
st.subheader("Ventas acumuladas del año")

ytd = (
    df[df["day_of_year"] <= cutoff_doy]
    .groupby(["year", "day_of_year"])["net_amount"]
    .sum()
    .groupby(level=0)
    .cumsum()
    .reset_index()
)

# Promedio histórico (todos menos el actual)
avg_years_ytd = [y for y in completed_years if y != 2022]
avg_ytd = (
    ytd[ytd["year"].isin(avg_years_ytd)]
    .groupby("day_of_year")["net_amount"]
    .mean()
    .reset_index()
)
avg_ytd["year"] = "Promedio histórico"

plot_ytd = pd.concat([
    ytd[ytd["year"].isin(last_two_years + [current_year])],
    avg_ytd
])

pivot_ytd = plot_ytd.pivot(
    index="day_of_year",
    columns="year",
    values="net_amount"
)

if pivot_ytd.empty:
    st.warning("No hay datos suficientes para mostrar el comparativo anual.")
else:
    # Convert day_of_year to actual dates (using current year as reference)
    ref_dates = pd.to_datetime(pivot_ytd.index.map(
        lambda d: f"{current_year}-01-01"
    )) + pd.to_timedelta(pivot_ytd.index - 1, unit="D")

    fig_ytd = go.Figure()
    for col in pivot_ytd.columns:
        dash = "dash" if col == "Promedio histórico" else None
        fig_ytd.add_trace(go.Scatter(
            x=ref_dates,
            y=pivot_ytd[col],
            name=str(col),
            mode="lines",
            line=dict(dash=dash),
            hovertemplate="<b>%{x|%d %b}</b> - %{meta}<br>$%{y:,.0f}<extra></extra>",
            meta=[str(col)] * len(pivot_ytd),
        ))
    fig_ytd.update_layout(
        xaxis_title="Fecha",
        yaxis_title="Ventas acumuladas",
        xaxis_tickformat="%d %b",
        yaxis_tickformat="$,.0f",
        height=400,
        legend_title="Año",
    )
    st.plotly_chart(fig_ytd, use_container_width=True)

# -----------------------------
# Bullets numéricos
# -----------------------------
st.markdown("### Este año vs años anteriores")

def ytd_total(year):
    return df[
        (df["year"] == year) &
        (df["day_of_year"] <= cutoff_doy)
    ]["net_amount"].sum()

cols = st.columns(3)

if len(last_two_years) == 2:
    cols[0].metric(
        f"{last_two_years[0]}",
        f"${ytd_total(last_two_years[0]):,.0f}"
    )
    cols[1].metric(
        f"{last_two_years[1]}",
        f"${ytd_total(last_two_years[1]):,.0f}"
    )

cols[2].metric(
    f"{current_year}",
    f"${ytd_total(current_year):,.0f}"
)