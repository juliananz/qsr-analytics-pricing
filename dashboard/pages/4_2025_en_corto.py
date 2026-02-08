import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(page_title="2025 en corto", layout="centered")

from auth import require_auth
require_auth()

# CSS personalizado para efecto "wrapped"
st.markdown("""
<style>
    .big-stat {
        font-size: 48px;
        font-weight: 700;
        text-align: center;
        margin: 20px 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .wrapped-section {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 30px;
        border-radius: 15px;
        color: white;
        margin: 20px 0;
        text-align: center;
    }
    .stat-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

st.title("🎧 Tu Año en Ventas")
st.caption("Un recorrido por tu año comercial")

# =================================================
# Disponibilidad temporal
# =================================================
today = datetime.today()

# Selector de año con radio buttons
st.markdown("### Selecciona el año que quieres revisar")

# Determinar año por defecto
if 'selected_year' not in st.session_state:
    if today.month in [1, 2]:
        default_year = 2025
    else:
        default_year = 2024
    st.session_state.selected_year = default_year

selected_year = st.radio(
    "Año",
    options=[2023, 2024, 2025],
    index=[2023, 2024, 2025].index(st.session_state.selected_year),
    horizontal=True,
    label_visibility="collapsed"
)

st.session_state.selected_year = selected_year

st.markdown(f"<h2 style='text-align: center; color: #667eea;'>📅 Resumen de {selected_year}</h2>", unsafe_allow_html=True)

# Advertencia solo si es 2025 y no estamos en enero/febrero
if selected_year == 2025 and today.month not in [1, 2]:
    st.info(
        "Nota: Estás viendo datos parciales de 2025. "
        "El resumen completo estará disponible en enero/febrero de 2026."
    )

# =================================================
# Carga de datos
# =================================================
@st.cache_data
def load_data():
    df = pd.read_parquet("data/analytics/fact_sales_margin.parquet")
    df["sale_date"] = pd.to_datetime(df["sale_date"])
    df["year"] = df["sale_date"].dt.year
    df["month"] = df["sale_date"].dt.month
    df["day_of_year"] = df["sale_date"].dt.dayofyear
    df["weekday"] = df["sale_date"].dt.day_name()
    return df

df = load_data()

# =================================================
# Definir periodo comparable
# =================================================
# Para el año seleccionado, usar todos los datos disponibles
cutoff = df[df["year"] == selected_year]["sale_date"].max()
cutoff_doy = cutoff.dayofyear

# Años para comparar: el seleccionado y los dos anteriores
compare_years = [selected_year - 2, selected_year - 1, selected_year]
compare_years = [y for y in compare_years if y in df["year"].unique()]

period_df = df[
    (df["year"].isin(compare_years)) &
    (df["day_of_year"] <= cutoff_doy)
]

df_selected = period_df[period_df["year"] == selected_year]

# =================================================
# 🎬 Intro - Los números grandes
# =================================================
st.markdown("""
<div class="wrapped-section">
    <h2>🎯 Empecemos con lo importante</h2>
    <p>Así se vivió el 2025 en números</p>
</div>
""", unsafe_allow_html=True)

sales_by_year = (
    period_df
    .groupby("year")["net_amount"]
    .sum()
    .sort_index()
)

sales_selected = sales_by_year.get(selected_year, 0)
sales_prev1 = sales_by_year.get(selected_year - 1, 0)
sales_prev2 = sales_by_year.get(selected_year - 2, 0)

st.markdown(f'<div class="big-stat">${sales_selected:,.0f}</div>', unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 20px; color: #666;'>en ventas totales</p>", unsafe_allow_html=True)

col1, col2 = st.columns(2)

growth_vs_prev1 = (sales_selected / sales_prev1 - 1) * 100 if sales_prev1 > 0 else 0
growth_vs_prev2 = (sales_selected / sales_prev2 - 1) * 100 if sales_prev2 > 0 else 0

with col1:
    st.markdown(f"""
    <div class="stat-card">
        <div style="font-size: 14px; color: #666;">vs {selected_year - 1}</div>
        <div style="font-size: 32px; font-weight: 600; color: {'#09ab3b' if growth_vs_prev1 > 0 else '#ff4b4b'};">
            {'+' if growth_vs_prev1 > 0 else ''}{growth_vs_prev1:.1f}%
        </div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="stat-card">
        <div style="font-size: 14px; color: #666;">vs {selected_year - 2}</div>
        <div style="font-size: 32px; font-weight: 600; color: {'#09ab3b' if growth_vs_prev2 > 0 else '#ff4b4b'};">
            {'+' if growth_vs_prev2 > 0 else ''}{growth_vs_prev2:.1f}%
        </div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# =================================================
# 📈 Curva del año
# =================================================
st.markdown("""
<div class="wrapped-section">
    <h2>📈 Tu año en una curva</h2>
    <p>Así fue el ritmo mes a mes</p>
</div>
""", unsafe_allow_html=True)

monthly_sales = (
    df_selected
    .groupby("month")["net_amount"]
    .sum()
    .reset_index()
)

month_names = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"
}
monthly_sales["month_name"] = monthly_sales["month"].map(month_names)

fig_monthly = go.Figure()
fig_monthly.add_trace(go.Scatter(
    x=monthly_sales["month_name"],
    y=monthly_sales["net_amount"],
    mode='lines+markers',
    line=dict(color='#667eea', width=3),
    marker=dict(size=10, color='#764ba2'),
    fill='tozeroy',
    fillcolor='rgba(102, 126, 234, 0.2)',
    hovertemplate='<b>%{x}</b><br>$%{y:,.0f}<extra></extra>'
))
fig_monthly.update_layout(
    height=300,
    showlegend=False,
    xaxis_title="Mes",
    yaxis_title="Ventas",
    margin=dict(l=0, r=0, t=0, b=0)
)
st.plotly_chart(fig_monthly, use_container_width=True)

best_month = monthly_sales.loc[monthly_sales["net_amount"].idxmax(), "month_name"]
best_month_sales = monthly_sales["net_amount"].max()

st.info(f"🏆 Tu mejor mes fue **{best_month}** con ${best_month_sales:,.0f} en ventas")

st.divider()

# =================================================
# 🔥 Lo más vendido
# =================================================
st.markdown("""
<div class="wrapped-section">
    <h2>🔥 Tus productos estrella</h2>
    <p>Estos fueron los que más brillaron</p>
</div>
""", unsafe_allow_html=True)

top_products = (
    df_selected
    .groupby("product_name")[["net_amount", "quantity"]]
    .sum()
    .sort_values("net_amount", ascending=False)
    .head(5)
    .reset_index()
)

top_products_display = top_products.copy()
top_products_display["net_amount"] = top_products_display["net_amount"].apply(lambda x: f"${x:,.0f}")
top_products_display["quantity"] = top_products_display["quantity"].apply(lambda x: f"{x:,.0f}")

top_products_display = top_products_display.rename(columns={
    "product_name": "Producto",
    "net_amount": "Ventas",
    "quantity": "Unidades"
})

st.dataframe(
    top_products_display,
    use_container_width=True,
    hide_index=True
)

# Producto #1
champion = top_products.iloc[0]
st.markdown(f"""
<div class="stat-card">
    <div style="font-size: 16px; color: #666;">🥇 Tu producto campeón</div>
    <div style="font-size: 24px; font-weight: 600; color: #667eea; margin: 10px 0;">
        {champion['product_name']}
    </div>
    <div style="font-size: 14px; color: #666;">
        Generó ${champion['net_amount']:,.0f} con {champion['quantity']:,.0f} unidades
    </div>
</div>
""", unsafe_allow_html=True)

st.divider()

# =================================================
# 💰 Los que más aportaron al margen
# =================================================
st.markdown("""
<div class="wrapped-section">
    <h2>💰 Tus generadores de margen</h2>
    <p>Estos hicieron crecer tu rentabilidad</p>
</div>
""", unsafe_allow_html=True)

margin_df = df_selected[df_selected["gross_margin"].notna()].copy()

top_margin = (
    margin_df
    .groupby("product_name")[["gross_margin", "net_amount"]]
    .sum()
    .sort_values("gross_margin", ascending=False)
    .head(5)
    .reset_index()
)

top_margin["margin_pct"] = (top_margin["gross_margin"] / top_margin["net_amount"] * 100)

top_margin_display = top_margin.copy()
top_margin_display["gross_margin"] = top_margin_display["gross_margin"].apply(lambda x: f"${x:,.0f}")
top_margin_display["margin_pct"] = top_margin_display["margin_pct"].apply(lambda x: f"{x:.1f}%")

top_margin_display = top_margin_display.rename(columns={
    "product_name": "Producto",
    "gross_margin": "Margen bruto",
    "margin_pct": "% Margen"
})[["Producto", "Margen bruto", "% Margen"]]

st.dataframe(
    top_margin_display,
    use_container_width=True,
    hide_index=True
)

total_margin = margin_df["gross_margin"].sum()
total_margin_pct = (total_margin / df_selected["net_amount"].sum() * 100)

st.markdown(f"""
<div class="stat-card">
    <div style="font-size: 16px; color: #666;">Margen bruto total del año</div>
    <div style="font-size: 32px; font-weight: 600; color: #09ab3b;">
        ${total_margin:,.0f}
    </div>
    <div style="font-size: 18px; color: #666;">
        {total_margin_pct:.1f}% de margen promedio
    </div>
</div>
""", unsafe_allow_html=True)

st.caption("ℹ️ Nota sobre margenes: Los costos actuales se aplican a todo el periodo historico. Precision total desde octubre 2025; periodos anteriores son una aproximacion consistente.")

st.divider()

# =================================================
# 📦 Historia de paquetes
# =================================================
st.markdown("""
<div class="wrapped-section">
    <h2>📦 El poder de los paquetes</h2>
    <p>¿Qué tanto vendiste en combos?</p>
</div>
""", unsafe_allow_html=True)

bundle_sales = df_selected[df_selected["bundle_code"].notna()]["net_amount"].sum()
bundle_share = (bundle_sales / sales_selected * 100) if sales_selected > 0 else 0

col_bundle1, col_bundle2 = st.columns(2)

with col_bundle1:
    st.markdown(f"""
    <div class="stat-card">
        <div style="font-size: 14px; color: #666;">Ventas en paquetes</div>
        <div style="font-size: 28px; font-weight: 600; color: #667eea;">
            ${bundle_sales:,.0f}
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_bundle2:
    st.markdown(f"""
    <div class="stat-card">
        <div style="font-size: 14px; color: #666;">% del total</div>
        <div style="font-size: 28px; font-weight: 600; color: #764ba2;">
            {bundle_share:.1f}%
        </div>
    </div>
    """, unsafe_allow_html=True)

if bundle_share > 30:
    st.success("🎉 ¡Los paquetes fueron una parte importante de tu estrategia!")
elif bundle_share > 10:
    st.info("💡 Los paquetes tienen potencial para crecer aún más")
else:
    st.warning("🤔 Hay oportunidad de impulsar más ventas con paquetes")

st.divider()

# =================================================
# 📅 Patrones de la semana
# =================================================
st.markdown("""
<div class="wrapped-section">
    <h2>📅 Tu día favorito de la semana</h2>
    <p>¿Cuándo vendiste más?</p>
</div>
""", unsafe_allow_html=True)

weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
weekday_spanish = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

weekday_sales = (
    df_selected
    .groupby("weekday")["net_amount"]
    .sum()
    .reindex(weekday_order)
    .reset_index()
)

weekday_sales["weekday_es"] = weekday_spanish

fig_weekday = go.Figure()
fig_weekday.add_trace(go.Bar(
    x=weekday_sales["weekday_es"],
    y=weekday_sales["net_amount"],
    marker_color=['#667eea' if i != weekday_sales["net_amount"].idxmax() else '#ff6b6b' 
                  for i in range(len(weekday_sales))],
    hovertemplate='<b>%{x}</b><br>$%{y:,.0f}<extra></extra>'
))
fig_weekday.update_layout(
    height=300,
    showlegend=False,
    xaxis_title="Día",
    yaxis_title="Ventas",
    margin=dict(l=0, r=0, t=0, b=0)
)
st.plotly_chart(fig_weekday, use_container_width=True)

best_day = weekday_sales.loc[weekday_sales["net_amount"].idxmax(), "weekday_es"]
best_day_sales = weekday_sales["net_amount"].max()

st.markdown(f"""
<div class="stat-card">
    <div style="font-size: 16px; color: #666;">Tu día más vendedor</div>
    <div style="font-size: 32px; font-weight: 600; color: #ff6b6b;">
        {best_day}
    </div>
    <div style="font-size: 14px; color: #666;">
        Con un promedio de ${best_day_sales / df_selected[df_selected['weekday'] == weekday_order[weekday_spanish.index(best_day)]]['sale_date'].nunique():,.0f} por día
    </div>
</div>
""", unsafe_allow_html=True)

st.divider()

# =================================================
# 🎯 El gran cierre
# =================================================
st.markdown(f"""
<div class="wrapped-section">
    <h2>🎯 Lo que nos dejó {selected_year}</h2>
    <p>Reflexiones de tu año comercial</p>
</div>
""", unsafe_allow_html=True)

insights = []

if sales_selected > sales_prev1:
    growth = ((sales_selected / sales_prev1 - 1) * 100)
    insights.append(f"📈 Creciste {growth:.1f}% vs {selected_year - 1}. El negocio va en la dirección correcta.")
else:
    decline = ((1 - sales_selected / sales_prev1) * 100) if sales_prev1 > 0 else 0
    insights.append(f"📉 Hubo una caída de {decline:.1f}% vs {selected_year - 1}. Tiempo de ajustar estrategias.")

if bundle_share > 50:
    insights.append("📦 Más de la mitad de tus ventas fueron paquetes. ¡Tu estrategia de combos funciona!")
elif bundle_share > 30:
    insights.append("📦 Los paquetes representaron una parte sólida de las ventas.")
else:
    insights.append("💡 Hay oportunidad de crear más paquetes atractivos.")

if total_margin_pct > 50:
    insights.append(f"💰 Con {total_margin_pct:.1f}% de margen, tu rentabilidad es excelente.")
elif total_margin_pct > 40:
    insights.append(f"💰 Un margen de {total_margin_pct:.1f}% es saludable. Mantén el enfoque.")
else:
    insights.append(f"⚠️ Tu margen de {total_margin_pct:.1f}% podría mejorar. Revisa costos y precios.")

# Consistencia mensual
monthly_variation = monthly_sales["net_amount"].std() / monthly_sales["net_amount"].mean() * 100
if monthly_variation < 20:
    insights.append("📊 Tus ventas fueron muy consistentes durante el año.")
elif monthly_variation < 40:
    insights.append("📊 Hubo cierta variación mes a mes, pero nada extremo.")
else:
    insights.append("📊 Tus ventas tuvieron altibajos importantes. Busca más estabilidad.")

for insight in insights:
    st.markdown(f"### {insight}")

st.divider()

st.markdown(f"""
<div class="wrapped-section">
    <h2>✨ Gracias por un {selected_year} increíble</h2>
    <p>Cada venta, cada producto, cada decisión contó una historia.</p>
    <p style="margin-top: 20px; font-size: 14px;">Ahora toca escribir el {selected_year + 1} 🚀</p>
</div>
""", unsafe_allow_html=True)

st.caption(
    "Este resumen busca contar la historia de tu año, "
    "no reemplazar el análisis detallado."
)