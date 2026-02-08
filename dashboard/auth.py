import streamlit as st
from streamlit_google_auth import Authenticate

def require_auth():
    authenticator = Authenticate(
        secret_credentials_file=None,
        cookie_name="qsr_auth",
        cookie_key=st.secrets["auth"]["cookie_secret"],
        redirect_uri=st.secrets["auth"]["redirect_uri"],
        client_id=st.secrets["auth"]["client_id"],
        client_secret=st.secrets["auth"]["client_secret"],
    )

    authenticator.check_authentification()

    if not st.session_state.get("connected", False):
        st.title("QSR Analytics")
        authenticator.login()
        st.stop()

    email = st.session_state.get("user_info", {}).get("email", "")
    allowed = st.secrets["auth"]["allowed_emails"]

    if email not in allowed:
        st.error(f"Access denied for {email}")
        st.stop()
