import streamlit as st
import hashlib
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId

# MongoDB Verbindung
@st.cache_resource
def init_db():
    try:
        client = MongoClient(st.secrets["MONGODB_URI"])
        # Test the connection
        client.admin.command('ping')
        db = client.interview_analyzer
        st.success("Mit Datenbank verbunden!")
        return db
    except Exception as e:
        st.error(f"Datenbankverbindung fehlgeschlagen: {str(e)}")
        return None

# Datenbank-Operationen
def create_user(username, password, email):
    """Erstellt einen neuen Benutzer"""
    db = init_db()
    
    # Prüfe ob Benutzer existiert
    if db.users.find_one({"username": username}):
        return False, "Benutzername bereits vergeben"
    
    # Erstelle neuen Benutzer
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

def check_credentials(username, password):
    """Überprüft die Anmeldedaten"""
    db = init_db()
    user = db.users.find_one({"username": username})
    
    if user and user['password'] == hash_password(password):
        return True
    return False

def get_user_projects(username):
    """Holt alle Projekte eines Benutzers"""
    db = init_db()
    return list(db.projects.find({"owner": username}))

def create_project(name, description, owner):
    """Erstellt ein neues Projekt"""
    db = init_db()
    
    # Prüfe ob Projekt existiert
    if db.projects.find_one({"name": name, "owner": owner}):
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

def save_analysis(project_id, transcript, analysis):
    """Speichert eine neue Analyse"""
    db = init_db()
    
    analysis_data = {
        'transcript': transcript,
        'analysis': analysis,
        'created': datetime.now()
    }
    
    db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$push": {"analyses": analysis_data}}
    )

# Rest des Codes bleibt größtenteils gleich, nur die Datenspeicherung wird angepasst
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

def test_db_connection():
    db = init_db()
    if db:
        # Erstelle Collections wenn sie nicht existieren
        if "users" not in db.list_collection_names():
            db.create_collection("users")
        if "projects" not in db.list_collection_names():
            db.create_collection("projects")
        return True
    return False