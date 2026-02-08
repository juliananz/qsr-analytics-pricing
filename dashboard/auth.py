"""
Authentication gate for QSR Analytics dashboard.

Uses Streamlit's built-in Google OAuth (st.login / st.user).
Requires [auth] section in Streamlit secrets with:
  - redirect_uri, cookie_secret, client_id, client_secret, server_metadata_url
  - allowed_emails (list of permitted Google email addresses)
"""

import streamlit as st


def require_auth():
    """Block page until user authenticates with an allowed Google account."""
    if not st.user.is_logged_in:
        st.title("QSR Analytics")
        st.caption("Inicia sesion con tu cuenta de Google para continuar.")
        st.button("Iniciar sesion con Google", on_click=st.login)
        st.stop()

    allowed = st.secrets["auth"].get("allowed_emails", [])
    if allowed and st.user.email not in allowed:
        st.error(f"Acceso denegado para {st.user.email}")
        st.button("Cerrar sesion", on_click=st.logout)
        st.stop()
