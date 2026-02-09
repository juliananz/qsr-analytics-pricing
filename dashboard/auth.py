import streamlit as st

def require_auth():
    # Trigger Google login if not authenticated
    if not st.user.is_logged_in:
        st.title("QSR Analytics")
        st.caption("Sign in with your Google account to continue.")
        st.login()
        st.stop()

    # Email whitelist
    allowed = st.secrets.get("app", {}).get("allowed_emails", [])
    if allowed and st.user.email not in allowed:
        st.error(f"Access denied for {st.user.email}")
        st.logout()
        st.stop()
