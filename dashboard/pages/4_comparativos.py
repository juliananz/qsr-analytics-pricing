import streamlit as st
import pandas as pd
from datetime import timedelta

# =================================================
# Configuración general
# =================================================
st.set_page_config(
    page_title="Comparativos",
    layout="centered"
)

st.title("📊 Comparativos")

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

current_year = cutoff.year
current_month = cutoff.month
current_month_name = cutoff.strftime("%B").capitalize()

# =================================================
# A. Ventas acumuladas YTD (gráfica + bullets)
# =================================================
st.subheader("Ventas acumuladas del año")

df["year"] = df["sale_date"].dt.year
df["day_of_year"] = df["sale_date"].dt.dayofyear

ytd = (
    df.groupby(["year", "day_of_year"])["net_amount"]
    .sum()
    .groupby(level=0)
    .cumsum()
    .reset_index()
)

# Años completos (excluye el actual)
completed_years = sorted(ytd["year"].unique())
completed_years = [y for y in completed_years if y < current_year]

# Últimos 2 años completos
last_two_years = completed_years[-2:]

# Promedio histórico (todos menos el actual)
avg_ytd = (
    ytd[ytd["year"].isin(completed_years)]
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
    st.line_chart(pivot_ytd)

# -----------------------------
# Bullets numéricos
# -----------------------------
st.markdown("### Resumen al día de hoy")

def ytd_total(year):
    return df[df["year"] == year]["net_amount"].sum()

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

# =================================================
# B. Mes actual vs mismo mes años anteriores
# =================================================
st.subheader(f"{current_month_name} vs {current_month_name.lower()}es anteriores")

month_df = df[df["sale_date"].dt.month == current_month].copy()
month_df["day"] = month_df["sale_date"].dt.day

month_acc = (
    month_df.groupby(["year", "day"])["net_amount"]
    .sum()
    .groupby(level=0)
    .cumsum()
    .reset_index()
)

avg_month = (
    month_acc[month_acc["year"].isin(completed_years)]
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
    st.line_chart(pivot_month)

# =================================================
# C. Semana actual vs semana pasada (barras lado a lado)
# =================================================
st.subheader("Semana actual vs semana pasada")

df["weekday"] = df["sale_date"].dt.weekday  # lunes = 0

current_week_start = cutoff - timedelta(days=cutoff.weekday())
prev_week_start = current_week_start - timedelta(days=7)

current_week = df[
    (df["sale_date"] >= current_week_start) &
    (df["sale_date"] <= cutoff)
]

prev_week = df[
    (df["sale_date"] >= prev_week_start) &
    (df["sale_date"] <= prev_week_start + timedelta(days=cutoff.weekday()))
]

week_compare = pd.DataFrame({
    "Semana pasada": prev_week.groupby("weekday")["net_amount"].sum(),
    "Semana actual": current_week.groupby("weekday")["net_amount"].sum()
}).fillna(0)

week_compare.index = [
    "Lunes", "Martes", "Miércoles",
    "Jueves", "Viernes", "Sábado", "Domingo"
][:len(week_compare)]

if week_compare.empty:
    st.warning("No hay datos suficientes para comparar semanas.")
else:
    st.bar_chart(week_compare)

# -----------------------------
# Interpretación automática
# -----------------------------
current_total = week_compare["Semana actual"].sum()
prev_total = week_compare["Semana pasada"].sum()

if prev_total > 0:
    diff_pct = (current_total - prev_total) / prev_total * 100
    if diff_pct > 3:
        st.success(f"Esta semana va {diff_pct:.1f}% arriba vs la semana pasada.")
    elif diff_pct < -3:
        st.warning(f"Esta semana va {abs(diff_pct):.1f}% abajo vs la semana pasada.")
    else:
        st.info("Esta semana va similar a la semana pasada.")
