import streamlit as st
from supabase import create_client
from datetime import datetime
import hashlib

# Supabase Setup
@st.cache_resource
def init_db():
    try:
        supabase = create_client(
            st.secrets["SUPABASE_URL"],
            st.secrets["SUPABASE_KEY"]
        )
        st.success("✅ Datenbankverbindung hergestellt!")
        return supabase
    except Exception as e:
        st.error(f"Datenbankverbindung fehlgeschlagen: {str(e)}")
        return None

def create_user(username, password, email):
    """Erstellt einen neuen Benutzer"""
    try:
        supabase = init_db()
        
        # Prüfe ob Benutzer existiert
        response = supabase.table('users').select('username').eq('username', username).execute()
        if len(response.data) > 0:
            return False, "Benutzername bereits vergeben"
        
        # Erstelle neuen Benutzer
        user_data = {
            'username': username,
            'password': hash_password(password),
            'email': email,
            'created_at': datetime.now().isoformat(),
            'profile': {
                'bio': '',
                'position': '',
                'company': ''
            }
        }
        
        supabase.table('users').insert(user_data).execute()
        return True, "Registrierung erfolgreich! Bitte loggen Sie sich ein."
    except Exception as e:
        return False, f"Fehler bei der Registrierung: {str(e)}"

def check_credentials(username, password):
    """Überprüft die Anmeldedaten"""
    try:
        supabase = init_db()
        response = supabase.table('users').select('password').eq('username', username).execute()
        
        if len(response.data) > 0 and response.data[0]['password'] == hash_password(password):
            return True
        return False
    except Exception as e:
        st.error(f"Fehler bei der Anmeldung: {str(e)}")
        return False

def create_project(name, description, owner):
    """Erstellt ein neues Projekt"""
    try:
        supabase = init_db()
        
        # Prüfe ob Projekt existiert
        response = supabase.table('projects').select('name').eq('name', name).eq('owner', owner).execute()
        if len(response.data) > 0:
            return False, "Ein Projekt mit diesem Namen existiert bereits!"
        
        project_data = {
            'name': name,
            'description': description,
            'owner': owner,
            'created_at': datetime.now().isoformat(),
            'analyses': []
        }
        
        supabase.table('projects').insert(project_data).execute()
        return True, "Projekt erfolgreich erstellt!"
    except Exception as e:
        return False, f"Fehler beim Erstellen des Projekts: {str(e)}"

def get_user_projects(username):
    """Holt alle Projekte eines Benutzers"""
    try:
        supabase = init_db()
        response = supabase.table('projects').select('*').eq('owner', username).execute()
        return response.data
    except Exception as e:
        st.error(f"Fehler beim Laden der Projekte: {str(e)}")
        return []