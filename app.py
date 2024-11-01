import streamlit as st
import whisper
import openai
import tempfile
import os
from datetime import datetime
from pymongo import MongoClient
import hashlib

# MongoDB Verbindung
@st.cache_resource
def init_db():
    try:
        # Verbindungsoptionen für SSL
        client = MongoClient(
            st.secrets["MONGODB_URI"],
            tls=True,
            tlsAllowInvalidCertificates=True,
            serverSelectionTimeoutMS=5000
        )
        # Test the connection
        client.admin.command('ping')
        return client.interview_analyzer
    except Exception as e:
        st.error(f"Datenbankverbindung fehlgeschlagen: {str(e)}")
        return None

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Benutzer-Management
def create_user(username, password, email):
    try:
        db = init_db()
        
        # Prüfe ob Benutzer existiert
        existing_user = db.users.find_one({"username": username})
        if existing_user:
            return False, "Benutzername bereits vergeben"
        
        user = {
            'username': username,
            'password': hash_password(password),
            'email': email,
            'created': datetime.now(),
            'profile': {
                'bio': '',
                'position': '',
                'company': ''
            }
        }
        
        db.users.insert_one(user)
        return True, "Registrierung erfolgreich! Bitte loggen Sie sich ein."
    except Exception as e:
        return False, f"Fehler bei der Registrierung: {str(e)}"

def check_credentials(username, password):
    try:
        db = init_db()
        user = db.users.find_one({"username": username})
        if user and user['password'] == hash_password(password):
            return True
        return False
    except Exception as e:
        st.error(f"Fehler bei der Anmeldung: {str(e)}")
        return False

# Projekt-Management
def create_project(name, description, owner):
    try:
        db = init_db()
        
        # Prüfe ob Projekt existiert
        existing_project = db.projects.find_one({"name": name, "owner": owner})
        if existing_project:
            return False, "Ein Projekt mit diesem Namen existiert bereits!"
        
        project = {
            'name': name,
            'description': description,
            'owner': owner,
            'created': datetime.now(),
            'analyses': []
        }
        
        db.projects.insert_one(project)
        return True, "Projekt erfolgreich erstellt!"
    except Exception as e:
        return False, f"Fehler beim Erstellen des Projekts: {str(e)}"

def get_user_projects(username):
    try:
        db = init_db()
        return list(db.projects.find({"owner": username}))
    except Exception as e:
        st.error(f"Fehler beim Laden der Projekte: {str(e)}")
        return []

# UI
def login():
    st.sidebar.title("🔐 Login")
    
    if not st.session_state.get('authenticated', False):
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
                create_project_btn = st.form_submit_button("Projekt erstellen")
                
                if create_project_btn and new_project:
                    success, message = create_project(new_project, project_description, st.session_state.current_user)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
        
        # Projekte anzeigen
        projects = get_user_projects(st.session_state.current_user)
        if projects:
            selected_project = st.sidebar.selectbox(
                "🎯 Projekt auswählen",
                options=[p['name'] for p in projects]
            )
            if selected_project:
                st.session_state.current_project = selected_project
        
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
    
    if not st.session_state.get('authenticated', False):
        st.warning("Bitte melden Sie sich an, um das Tool zu nutzen.")
        return
    
    if not st.session_state.get('current_project'):
        st.info("Bitte wählen Sie ein Projekt aus oder erstellen Sie ein neues.")
        return
    
    # Hauptbereich für Video-Upload und Analyse
    st.write(f"🎯 Aktives Projekt: **{st.session_state.current_project}**")
    
    if 'processed_files' not in st.session_state:
        st.session_state.processed_files = set()
    if 'transcripts' not in st.session_state:
        st.session_state.transcripts = {}
    
    uploaded_file = st.file_uploader("Video hochladen (max 100MB)", type=['mp4', 'mov', 'avi'])
    
    if uploaded_file is not None:
        file_hash = hash(uploaded_file.getvalue())
        
        # Container für Status-Updates
        status_container = st.empty()
        
        if file_hash in st.session_state.processed_files:
            status_container.info("🔄 Diese Datei wurde bereits verarbeitet")
            transcript = st.session_state.transcripts.get(file_hash, "")
            
            if st.button("🔄 Neu analysieren"):
                status_container.info("⏳ Analyse wird durchgeführt...")
                
                try:
                    analysis = analyze_transcript(transcript)
                    status_container.success("✅ Analyse abgeschlossen!")
                    
                    with st.expander("📝 Transkription", expanded=False):
                        st.text_area("", transcript, height=200)
                    
                    with st.expander("🔍 Analyse", expanded=True):
                        st.markdown(analysis)
                except Exception as e:
                    status_container.error(f"❌ Fehler bei der Analyse: {str(e)}")
        else:
            try:
                # Temporäre Datei erstellen
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    video_path = tmp_file.name
                
                status_container.info("⏳ Transkription wird erstellt...")
                
                # Whisper Transkription
                model = whisper.load_model("base")
                result = model.transcribe(video_path)
                transcript = result["text"]
                
                # Speichern der Transkription
                st.session_state.processed_files.add(file_hash)
                st.session_state.transcripts[file_hash] = transcript
                
                # Cleanup
                os.unlink(video_path)
                
                # GPT Analyse
                status_container.info("⏳ Analyse wird durchgeführt...")
                analysis = analyze_transcript(transcript)
                
                status_container.success("✅ Analyse abgeschlossen!")
                
                # Ergebnisse anzeigen
                with st.expander("📝 Transkription", expanded=False):
                    st.text_area("", transcript, height=200)
                
                with st.expander("🔍 Analyse", expanded=True):
                    st.markdown(analysis)
                
                # Speichern in der Datenbank
                save_analysis_to_db(
                    st.session_state.current_project,
                    transcript,
                    analysis
                )
                
                # Erfolgsanimation
                st.balloons()
            
            except Exception as e:
                status_container.error(f"❌ Fehler bei der Verarbeitung: {str(e)}")
                if 'video_path' in locals():
                    os.unlink(video_path)
    
    # Hier kommt Ihr bestehender Code für Video-Upload und Analyse

if __name__ == "__main__":
    main()