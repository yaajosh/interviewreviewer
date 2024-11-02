import streamlit as st
import tempfile
import os
from datetime import datetime
from supabase import create_client
import openai
import warnings
warnings.filterwarnings("ignore")

# Basis-Konfiguration
st.set_page_config(
    page_title="Interview Analyzer",
    page_icon="🎯",
    layout="wide"
)

# Minimales CSS
st.markdown("""
<style>
    .stButton button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# Supabase Setup
@st.cache_resource
def init_supabase():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

def sign_up(email, password):
    try:
        supabase = init_supabase()
        response = supabase.auth.sign_up({
            "email": email,
            "password": password
        })
        if response.user:
            return True, "Registrierung erfolgreich!"
        return False, "Registrierung fehlgeschlagen"
    except Exception as e:
        return False, str(e)

def sign_in(email, password):
    try:
        supabase = init_supabase()
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        if response.user:
            return True, response.user
        return False, "Login fehlgeschlagen"
    except Exception as e:
        return False, str(e)

def login():
    if not st.session_state.get('authenticated', False):
        with st.sidebar:
            tab1, tab2 = st.tabs(["Login", "Registrierung"])
            
            with tab1:
                with st.form("login_form"):
                    email = st.text_input("Email")
                    password = st.text_input("Passwort", type="password")
                    if st.form_submit_button("Anmelden"):
                        success, result = sign_in(email, password)
                        if success:
                            st.session_state.authenticated = True
                            st.session_state.user = result
                            st.rerun()
                        else:
                            st.error(result)
            
            with tab2:
                with st.form("register_form"):
                    email = st.text_input("Email")
                    password = st.text_input("Passwort", type="password")
                    password2 = st.text_input("Passwort wiederholen", type="password")
                    if st.form_submit_button("Registrieren"):
                        if password != password2:
                            st.error("Passwörter stimmen nicht überein")
                        else:
                            success, message = sign_up(email, password)
                            if success:
                                st.success(message)
                            else:
                                st.error(message)
    else:
        with st.sidebar:
            st.write(f"Eingeloggt als: {st.session_state.user.email}")
            if st.button("Ausloggen"):
                st.session_state.clear()
                st.rerun()

def main():
    st.title("Interview Analyzer")
    
    # Login-System
    login()
    
    # Hauptbereich nur anzeigen wenn eingeloggt
    if st.session_state.get('authenticated', False):
        st.write("Willkommen! Sie sind eingeloggt.")
    else:
        st.info("Bitte melden Sie sich an.")

if __name__ == "__main__":
    main()