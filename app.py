import streamlit as st
import whisper
import openai
import tempfile
import os
import json
from datetime import datetime
import hashlib

# Initialisiere Session State
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'current_project' not in st.session_state:
    st.session_state.current_project = None
if 'projects' not in st.session_state:
    st.session_state.projects = {}

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username, password, email):
    """Erstellt einen neuen Benutzer"""
    users = dict(st.secrets.get("USERS", {}))
    
    if username in users:
        return False, "Benutzername bereits vergeben"
    
    hashed_password = hash_password(password)
    
    # Speichere in Session State für sofortige Nutzung
    st.session_state.temp_users = st.session_state.get('temp_users', {})
    st.session_state.temp_users[username] = {
        'password': hashed_password,
        'email': email
    }
    
    return True, "Registrierung erfolgreich! Bitte loggen Sie sich ein."

def check_credentials(username, password):
    """Überprüft die Anmeldedaten"""
    users = dict(st.secrets.get("USERS", {}))
    temp_users = st.session_state.get('temp_users', {})
    
    # Prüfe temporäre und permanente Benutzer
    if username in users:
        stored_password = users[username]
        return stored_password == hash_password(password)
    elif username in temp_users:
        stored_password = temp_users[username]['password']
        return stored_password == hash_password(password)
    return False

def login():
    st.sidebar.title("🔐 Login")
    
    if not st.session_state.authenticated:
        tab1, tab2 = st.sidebar.tabs(["🔑 Login", "📝 Registrierung"])
        
        with tab1:
            with st.form("login_form"):
                username = st.text_input("Benutzername")
                password = st.text_input("Passwort", type="password")
                submit = st.form_submit_button("Anmelden")
                
                if submit:
                    if check_credentials(username, password):
                        st.session_state.authenticated = True
                        st.session_state.current_user = username
                        st.experimental_rerun()
                    else:
                        st.error("Falsche Anmeldedaten!")
        
        with tab2:
            with st.form("register_form"):
                new_username = st.text_input("Benutzername")
                new_password = st.text_input("Passwort", type="password")
                confirm_password = st.text_input("Passwort bestätigen", type="password")
                email = st.text_input("E-Mail")
                register = st.form_submit_button("Registrieren")
                
                if register:
                    if not new_username or not new_password:
                        st.error("Bitte füllen Sie alle Felder aus!")
                    elif new_password != confirm_password:
                        st.error("Passwörter stimmen nicht überein!")
                    else:
                        success, message = create_user(new_username, new_password, email)
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
    
    else:
        st.sidebar.success(f"✅ Eingeloggt als {st.session_state.current_user}")
        
        if st.sidebar.button("Ausloggen"):
            st.session_state.authenticated = False
            st.session_state.current_user = None
            st.session_state.current_project = None
            st.experimental_rerun()

def main():
    st.title("User Interview Analyse Tool")
    
    # Login und Projekt Management
    login()
    
    if not st.session_state.authenticated:
        st.warning("Bitte melden Sie sich an, um das Tool zu nutzen.")
        return
    
    if not st.session_state.current_project:
        st.warning("Bitte wählen Sie ein Projekt aus oder erstellen Sie ein neues.")
        return
    
    if 'processed_files' not in st.session_state:
        st.session_state.processed_files = set()
    if 'transcripts' not in st.session_state:
        st.session_state.transcripts = {}
    
    uploaded_file = st.file_uploader("Video hochladen (max 100MB)", type=['mp4', 'mov', 'avi'])
    
    if uploaded_file is not None:
        file_hash = hash(uploaded_file.getvalue())
        
        if file_hash in st.session_state.processed_files:
            st.info("Diese Datei wurde bereits transkribiert. Starte direkt die Analyse...")
            
            # Hole gespeicherte Transkription
            transcript = st.session_state.transcripts.get(file_hash)
            
            if st.button("Neu analysieren"):
                status_container = st.empty()
                result_container = st.empty()
                
                # GPT Analyse
                with status_container:
                    st.info("🧠 Analysiere mit GPT-4...")
                
                analysis = summarize_with_gpt(transcript)
                
                # Zeige Ergebnisse
                status_container.empty()
                
                with result_container.container():
                    st.success("✅ Analyse abgeschlossen!")
                    
                    # Transkription
                    with st.expander("📝 Transkription", expanded=False):
                        st.text_area("", transcript, height=200)
                    
                    # GPT Analyse
                    with st.expander("🔍 Analyse", expanded=True):
                        st.markdown(analysis)
                    
                    # Erfolgsanimation
                    st.balloons()
        else:
            if st.button("Analysieren"):
                status_container = st.empty()
                progress_container = st.empty()
                result_container = st.empty()
                
                with status_container:
                    st.info("🎬 Verarbeite Interview...")
                
                # Transkription
                transcript = transcribe_video(uploaded_file)
                
                if transcript:
                    # Speichere Transkription
                    st.session_state.processed_files.add(file_hash)
                    st.session_state.transcripts[file_hash] = transcript
                    
                    # GPT Analyse
                    with status_container:
                        st.info("🧠 Analysiere mit GPT-4...")
                    
                    analysis = summarize_with_gpt(transcript)
                    
                    # Zeige Ergebnisse
                    status_container.empty()
                    progress_container.empty()
                    
                    with result_container.container():
                        st.success("✅ Analyse abgeschlossen!")
                        
                        # Transkription
                        with st.expander("📝 Transkription", expanded=False):
                            st.text_area("", transcript, height=200)
                        
                        # GPT Analyse
                        with st.expander("🔍 Analyse", expanded=True):
                            st.markdown(analysis)
                        
                        # Erfolgsanimation
                        st.balloons()
                else:
                    status_container.error("❌ Fehler bei der Verarbeitung")

if __name__ == "__main__":
    main() 