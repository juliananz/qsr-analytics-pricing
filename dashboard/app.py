import streamlit as st

# =================================================
# Configuración general de la app
# =================================================
st.set_page_config(
    page_title="QSR Analytics",
    page_icon="🍔",
    layout="centered",
    initial_sidebar_state="expanded"
)

# =================================================
# Portada
# =================================================
st.title("🍔 QSR Analytics & Pricing")
st.caption(
    "Dashboard operativo para control de ventas, márgenes y rentabilidad"
)

st.markdown(
    """
    **¿Qué puedes hacer aquí?**
    
    - Revisar cómo va el negocio hoy y esta semana  
    - Comparar ventas contra años anteriores  
    - Identificar productos y paquetes clave  
    - Analizar sensibilidad a cambios de costos y precios  

    👉 Usa el menú lateral para navegar.
    """
)

st.divider()

st.info(
    "Este dashboard se actualiza automáticamente cuando se cargan nuevas ventas."
)
