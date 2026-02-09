import json
import tempfile
import os

import streamlit as st
from streamlit_google_auth import Authenticate


def _get_credentials_path():
    """Build a Google OAuth client-secrets JSON file from Streamlit secrets.

    streamlit-google-auth requires a file path (it calls
    google_auth_oauthlib.flow.Flow.from_client_secrets_file internally).
    On Streamlit Cloud there is no credentials file on disk, so we
    construct one at runtime from st.secrets and write it to a temp file.
    The file is created once per process and reused.
    """
    path = os.path.join(tempfile.gettempdir(), "google_client_secret.json")
    if not os.path.exists(path):
        payload = {
            "web": {
                "client_id": st.secrets["auth"]["client_id"],
                "client_secret": st.secrets["auth"]["client_secret"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [st.secrets["auth"]["redirect_uri"]],
            }
        }
        with open(path, "w") as f:
            json.dump(payload, f)
    return path


def require_auth():
    authenticator = Authenticate(
        secret_credentials_path=_get_credentials_path(),
        cookie_name="qsr_auth",
        cookie_key=st.secrets["auth"]["cookie_secret"],
        redirect_uri=st.secrets["auth"]["redirect_uri"],
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
