import streamlit as st
import whisper
import openai
import tempfile
import os
from datetime import datetime
from supabase import create_client
import uuid

# Supabase Setup
@st.cache_resource
def init_supabase():
    try:
        return create_client(
            st.secrets["SUPABASE_URL"],
            st.secrets["SUPABASE_KEY"]
        )
    except Exception as e:
        st.error(f"Datenbankverbindung fehlgeschlagen: {str(e)}")
        return None

def sign_up(email, password):
    """Registriert einen neuen Benutzer"""
    try:
        supabase = init_supabase()
        response = supabase.auth.sign_up({
            "email": email,
            "password": password
        })
        
        if response.user:
            # Erstelle Profil
            profile_data = {
                "id": response.user.id,
                "email": email,
                "username": email.split('@')[0],  # Einfacher Username aus Email
            }
            supabase.table('profiles').insert(profile_data).execute()
            
            return True, "Registrierung erfolgreich! Bitte bestätigen Sie Ihre E-Mail."
    except Exception as e:
        return False, f"Fehler bei der Registrierung: {str(e)}"

def sign_in(email, password):
    """Meldet einen Benutzer an"""
    try:
        supabase = init_supabase()
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        if response.user:
            return True, response.user
        return False, "Anmeldung fehlgeschlagen"
    except Exception as e:
        return False, f"Fehler bei der Anmeldung: {str(e)}"

def get_user_projects(user_id):
    """Holt alle Projekte eines Benutzers"""
    try:
        supabase = init_supabase()
        response = supabase.table('projects').select('*').eq('owner_id', user_id).execute()
        return response.data
    except Exception as e:
        st.error(f"Fehler beim Laden der Projekte: {str(e)}")
        return []

def create_project(name, description, owner_id):
    """Erstellt ein neues Projekt"""
    try:
        supabase = init_supabase()
        project_data = {
            "name": name,
            "description": description,
            "owner_id": owner_id
        }
        
        response = supabase.table('projects').insert(project_data).execute()
        return True, "Projekt erfolgreich erstellt!"
    except Exception as e:
        return False, f"Fehler beim Erstellen des Projekts: {str(e)}"

def login():
    st.sidebar.title("🔐 Login")
    
    if not st.session_state.get('authenticated', False):
        tab1, tab2 = st.sidebar.tabs(["🔑 Login", "📝 Registrierung"])
        
        with tab1:
            with st.form("login_form"):
                email = st.text_input("E-Mail")
                password = st.text_input("Passwort", type="password")
                submit = st.form_submit_button("Anmelden")
                
                if submit:
                    success, result = sign_in(email, password)
                    if success:
                        st.session_state.authenticated = True
                        st.session_state.user = result
                        st.rerun()
                    else:
                        st.error(result)
        
        with tab2:
            with st.form("register_form"):
                email = st.text_input("E-Mail")
                password = st.text_input("Passwort", type="password")
                confirm_password = st.text_input("Passwort bestätigen", type="password")
                register = st.form_submit_button("Registrieren")
                
                if register:
                    if not email or not password:
                        st.error("Bitte füllen Sie alle Felder aus!")
                    elif password != confirm_password:
                        st.error("Passwörter stimmen nicht überein!")
                    else:
                        success, message = sign_up(email, password)
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
    
    else:
        user = st.session_state.user
        st.sidebar.success(f"✅ Eingeloggt als {user.email}")
        
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
                    success, message = create_project(
                        new_project, 
                        project_description, 
                        user.id
                    )
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
        
        # Projekte anzeigen
        projects = get_user_projects(user.id)
        if projects:
            selected_project = st.sidebar.selectbox(
                "🎯 Projekt auswählen",
                options=[p['name'] for p in projects],
                key='project_selector'
            )
            if selected_project:
                st.session_state.current_project = selected_project
        
        # Ausloggen
        if st.sidebar.button("Ausloggen"):
            supabase = init_supabase()
            supabase.auth.sign_out()
            st.session_state.clear()
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

def analyze_transcript(transcript):
    """Analysiert die Transkription mit GPT-4"""
    prompt = f"""
    Analysiere das folgende User Interview und erstelle eine strukturierte Zusammenfassung:
    
    {transcript}
    
    Bitte strukturiere die Analyse wie folgt:
    1. Haupterkenntnisse (3-5 Punkte)
    2. Schmerzpunkte des Nutzers
    3. Vorgeschlagene Lösungen/Wünsche
    4. Interessante Zitate
    5. Empfehlungen für nächste Schritte
    """
    
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Du bist ein erfahrener UX Researcher, der User Interviews analysiert."},
            {"role": "user", "content": prompt}
        ]
    )
    
    return response.choices[0].message.content

if __name__ == "__main__":
    main()