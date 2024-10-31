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
    """Einfache Passwort-Hashfunktion"""
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username, password, email):
    """Erstellt einen neuen Benutzer"""
    # Lade aktuelle Benutzer aus secrets.toml
    users = dict(st.secrets.get("USERS", {}))
    
    if username in users:
        return False, "Benutzername bereits vergeben"
    
    # Füge neuen Benutzer hinzu
    users[username] = {
        'password': hash_password(password),
        'email': email,
        'created': datetime.now().strftime("%Y-%m-%d %H:%M"),
        'profile': {
            'bio': '',
            'position': '',
            'company': ''
        },
        'shared_projects': []
    }
    
    # Speichere in secrets.toml
    with open('.streamlit/secrets.toml', 'a') as f:
        f.write(f'\n[USERS.{username}]\n')
        f.write(f'password = "{users[username]["password"]}"\n')
        f.write(f'email = "{email}"\n')
    
    return True, "Registrierung erfolgreich"

def check_credentials(username, password):
    """Überprüft die Anmeldedaten gegen die gespeicherten Secrets"""
    users = dict(st.secrets.get("USERS", {}))
    if username in users:
        stored_password = users[username].get('password', users[username])  # Unterstützt beide Formate
        return stored_password == hash_password(password)
    return False

def login():
    st.sidebar.title("🔐 Login")
    
    # Login Bereich
    if not st.session_state.authenticated:
        with st.sidebar.form("login_form"):
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
    
    # Projekt Management (nur wenn eingeloggt)
    if st.session_state.authenticated:
        st.sidebar.success(f"✅ Eingeloggt als {st.session_state.current_user}")
        
        # Logout Button
        if st.sidebar.button("Ausloggen"):
            st.session_state.authenticated = False
            st.session_state.current_user = None
            st.session_state.current_project = None
            st.experimental_rerun()
        
        st.sidebar.markdown("---")
        st.sidebar.title("📊 Projekt Manager")
        
        # Neues Projekt erstellen
        with st.sidebar.expander("➕ Neues Projekt"):
            new_project = st.text_input("Projektname")
            if st.button("Projekt erstellen") and new_project:
                project_key = f"{st.session_state.current_user}_{new_project}"
                if project_key not in st.session_state.projects:
                    st.session_state.projects[project_key] = {
                        'name': new_project,
                        'owner': st.session_state.current_user,
                        'created': datetime.now().strftime("%Y-%m-%d %H:%M"),
                        'analyses': {}
                    }
                    st.success(f"Projekt '{new_project}' erstellt!")
                    st.experimental_rerun()
        
        # Projekt auswählen (nur eigene Projekte)
        user_projects = {k: v for k, v in st.session_state.projects.items() 
                        if v['owner'] == st.session_state.current_user}
        
        if user_projects:
            project_names = [v['name'] for v in user_projects.values()]
            selected_project = st.sidebar.selectbox(
                "🎯 Projekt auswählen",
                project_names
            )
            
            if selected_project:
                project_key = f"{st.session_state.current_user}_{selected_project}"
                if project_key != st.session_state.current_project:
                    st.session_state.current_project = project_key
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