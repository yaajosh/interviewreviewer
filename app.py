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

def create_project(name, description, owner_id):
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
        return False, str(e)

def get_user_projects(user_id):
    try:
        supabase = init_supabase()
        response = supabase.table('projects').select('*').eq('owner_id', user_id).execute()
        return response.data
    except Exception as e:
        st.error(f"Fehler beim Laden der Projekte: {str(e)}")
        return []

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
            # Profil-Bereich
            st.write(f"Eingeloggt als: {st.session_state.user.email}")
            
            st.divider()
            
            # Projekte-Bereich
            st.subheader("📂 Projekte")
            
            # Neues Projekt
            if st.button("+ Neues Projekt"):
                st.session_state.show_new_project = True
                
            # Modal für neues Projekt
            if st.session_state.get('show_new_project', False):
                with st.form("new_project"):
                    project_name = st.text_input("Projektname")
                    project_desc = st.text_area("Beschreibung")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("Erstellen"):
                            if project_name:
                                success, msg = create_project(
                                    project_name,
                                    project_desc,
                                    st.session_state.user.id
                                )
                                if success:
                                    st.success(msg)
                                    st.session_state.show_new_project = False
                                    st.rerun()
                                else:
                                    st.error(msg)
                    with col2:
                        if st.form_submit_button("Abbrechen"):
                            st.session_state.show_new_project = False
                            st.rerun()
            
            # Projekte Liste
            projects = get_user_projects(st.session_state.user.id)
            if projects:
                for project in projects:
                    if st.button(f"📁 {project['name']}", key=project['name']):
                        st.session_state.current_project = project['name']
                        st.rerun()
            else:
                st.info("Noch keine Projekte vorhanden")
            
            st.divider()
            
            if st.button("🚪 Ausloggen"):
                st.session_state.clear()
                st.rerun()

@st.cache_resource
def load_whisper():
    try:
        import whisper
        model = whisper.load_model("base")
        return model
    except Exception as e:
        st.error(f"Fehler beim Laden des Whisper Models: {str(e)}")
        return None

def transcribe_video(video_path):
    try:
        model = load_whisper()
        if model is None:
            return None
        result = model.transcribe(video_path)
        return result["text"]
    except Exception as e:
        st.error(f"Fehler bei der Transkription: {str(e)}")
        return None

def analyze_transcript(transcript):
    try:
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
    except Exception as e:
        st.error(f"Fehler bei der Analyse: {str(e)}")
        return None

def save_analysis_to_db(project_name, transcript, analysis):
    try:
        supabase = init_supabase()
        analysis_data = {
            'transcript': transcript,
            'analysis': analysis,
            'created_at': datetime.now().isoformat()
        }
        
        response = supabase.table('projects').select('analyses').eq('name', project_name).execute()
        if len(response.data) > 0:
            analyses = response.data[0].get('analyses', [])
            if not analyses:
                analyses = []
            analyses.append(analysis_data)
            
            supabase.table('projects').update({'analyses': analyses}).eq('name', project_name).execute()
            return True
        return False
    except Exception as e:
        st.error(f"Fehler beim Speichern: {str(e)}")
        return False

def get_project_analyses(project_name):
    try:
        supabase = init_supabase()
        response = supabase.table('projects').select('analyses').eq('name', project_name).execute()
        if response.data and len(response.data) > 0:
            return response.data[0].get('analyses', [])
        return []
    except Exception as e:
        st.error(f"Fehler beim Laden der Analysen: {str(e)}")
        return []

def main():
    st.title("Interview Analyzer")
    
    login()
    
    if st.session_state.get('authenticated', False):
        if st.session_state.get('current_project'):
            # Projekt Header
            st.markdown(f"""
                ### 🎯 Projekt: {st.session_state.current_project}
                ---
            """)
            
            # Zwei Spalten: Analysen Tabelle und Neue Analyse Button
            col1, col2 = st.columns([3, 1])
            
            with col2:
                # Neue Analyse Button
                if st.button("➕ Neue Analyse", type="primary", use_container_width=True):
                    st.session_state.show_upload = True
            
            with col1:
                # Analysen Tabelle
                analyses = get_project_analyses(st.session_state.current_project)
                if analyses:
                    st.markdown("### 📊 Bisherige Analysen")
                    
                    # Erstelle DataFrame für bessere Darstellung
                    import pandas as pd
                    analyses_data = []
                    for idx, analysis in enumerate(analyses, 1):
                        date = datetime.fromisoformat(analysis['created_at']).strftime('%d.%m.%Y %H:%M')
                        analyses_data.append({
                            "Nr.": idx,
                            "Datum": date,
                            "Details": "Anzeigen"
                        })
                    
                    df = pd.DataFrame(analyses_data)
                    st.dataframe(
                        df,
                        column_config={
                            "Nr.": st.column_config.NumberColumn(width=50),
                            "Datum": st.column_config.TextColumn(width=150),
                            "Details": st.column_config.ButtonColumn(width=100)
                        },
                        hide_index=True
                    )
                    
                    # Wenn auf Details geklickt wird
                    if "Details" in st.session_state.get("clicked_button", ""):
                        idx = int(st.session_state.clicked_button.split("-")[1]) - 1
                        analysis = analyses[idx]
                        with st.expander("📝 Analyse Details", expanded=True):
                            st.markdown("**Transkription:**")
                            st.text_area("", analysis['transcript'], height=150)
                            st.markdown("**Analyse:**")
                            st.markdown(analysis['analysis'])
                else:
                    st.info("Noch keine Analysen vorhanden")
            
            # Video Upload und Analyse Bereich
            if st.session_state.get('show_upload', False):
                st.markdown("---")
                st.markdown("### 🎥 Neue Analyse")
                
                uploaded_file = st.file_uploader(
                    "Video hochladen (MP4, MOV, AVI)", 
                    type=['mp4', 'mov', 'avi']
                )
                
                if uploaded_file:
                    # Progress Container
                    progress_container = st.empty()
                    
                    # Datei-Hash für Cache
                    file_hash = hash(uploaded_file.getvalue())
                    
                    if file_hash in st.session_state.get('processed_files', set()):
                        progress_container.info("🔄 Diese Datei wurde bereits verarbeitet")
                        transcript = st.session_state.transcripts.get(file_hash, "")
                        
                        if st.button("🔄 Neu analysieren"):
                            progress_container.info("⏳ Analyse wird durchgeführt...")
                            analysis = analyze_transcript(transcript)
                            if analysis:
                                progress_container.success("✅ Analyse abgeschlossen!")
                                
                                with st.expander("📝 Transkription", expanded=False):
                                    st.text_area("", transcript, height=200)
                                
                                with st.expander("🔍 Analyse", expanded=True):
                                    st.markdown(analysis)
                                
                                if save_analysis_to_db(st.session_state.current_project, transcript, analysis):
                                    st.success("✅ Analyse wurde gespeichert!")
                                    st.balloons()
                    
                    else:
                        try:
                            # Temporäre Datei erstellen
                            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
                                tmp_file.write(uploaded_file.getvalue())
                                video_path = tmp_file.name
                            
                            progress_container.info("⏳ Transkription wird erstellt...")
                            transcript = transcribe_video(video_path)
                            
                            if transcript:
                                # Cache-Verwaltung
                                if 'processed_files' not in st.session_state:
                                    st.session_state.processed_files = set()
                                if 'transcripts' not in st.session_state:
                                    st.session_state.transcripts = {}
                                    
                                st.session_state.processed_files.add(file_hash)
                                st.session_state.transcripts[file_hash] = transcript
                                
                                progress_container.info("⏳ Analyse wird durchgeführt...")
                                analysis = analyze_transcript(transcript)
                                
                                if analysis:
                                    progress_container.success("✅ Analyse abgeschlossen!")
                                    
                                    with st.expander("📝 Transkription", expanded=False):
                                        st.text_area("", transcript, height=200)
                                    
                                    with st.expander("🔍 Analyse", expanded=True):
                                        st.markdown(analysis)
                                    
                                    if save_analysis_to_db(st.session_state.current_project, transcript, analysis):
                                        st.success("✅ Analyse wurde gespeichert!")
                                        st.balloons()
                        
                        # Cleanup
                        os.unlink(video_path)
                        
                    except Exception as e:
                        progress_container.error(f"❌ Fehler: {str(e)}")
                        if 'video_path' in locals():
                            os.unlink(video_path)
                if st.button("❌ Abbrechen"):
                    st.session_state.show_upload = False
                    st.rerun()
        else:
            st.info("Bitte wählen Sie ein Projekt aus oder erstellen Sie ein neues.")
    else:
        st.info("Bitte melden Sie sich an.")

if __name__ == "__main__":
    main()