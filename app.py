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
                        st.rerun()
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
        
        # Projekt Management
        st.sidebar.markdown("---")
        st.sidebar.title("📊 Projekt Manager")
        
        # Neues Projekt erstellen
        with st.sidebar.expander("➕ Neues Projekt"):
            with st.form("new_project_form"):
                new_project = st.text_input("Projektname")
                project_description = st.text_area("Projektbeschreibung", height=100)
                create_project = st.form_submit_button("Projekt erstellen")
                
                if create_project and new_project:
                    project_key = f"{st.session_state.current_user}_{new_project}"
                    if project_key not in st.session_state.projects:
                        st.session_state.projects[project_key] = {
                            'name': new_project,
                            'description': project_description,
                            'owner': st.session_state.current_user,
                            'created': datetime.now().strftime("%Y-%m-%d %H:%M"),
                            'analyses': {}
                        }
                        st.success(f"Projekt '{new_project}' erstellt!")
                        st.rerun()
                    else:
                        st.error("Ein Projekt mit diesem Namen existiert bereits!")
        
        # Projekt auswählen
        if st.session_state.projects:
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
                        st.rerun()
        
        # Ausloggen
        if st.sidebar.button("Ausloggen"):
            st.session_state.authenticated = False
            st.session_state.current_user = None
            st.session_state.current_project = None
            st.rerun()

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
    
    # Zeige aktives Projekt
    project = st.session_state.projects[st.session_state.current_project]
    st.write(f"🎯 Aktives Projekt: **{project['name']}**")
    
    # Projekt Details
    with st.expander("📋 Projekt Details", expanded=False):
        st.write(f"**Beschreibung:** {project['description']}")
        st.write(f"**Erstellt am:** {project['created']}")
        st.write(f"**Besitzer:** {project['owner']}")
        st.write(f"**Analysen:** {len(project['analyses'])}")

if __name__ == "__main__":
    main() 