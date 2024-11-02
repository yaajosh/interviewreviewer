import streamlit as st
import tempfile
import os
from datetime import datetime
from supabase import create_client
import openai
import warnings
import random
import time
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

# Datenbank-Updates
def init_db():
    supabase = init_supabase()
    # Analyses als separate Tabelle
    supabase.table('analyses').create({
        'id': 'uuid default uuid_generate_v4() primary key',
        'project_id': 'uuid references projects(id)',
        'status': 'text default "pending"',
        'transcript': 'text',
        'analysis': 'text',
        'created_at': 'timestamp with time zone default now()',
        'updated_at': 'timestamp with time zone default now()'
    })

def create_analysis(project_id, file_hash):
    try:
        supabase = init_supabase()
        analysis_data = {
            'project_id': project_id,
            'status': 'pending',
            'file_hash': file_hash
        }
        response = supabase.table('analyses').insert(analysis_data).execute()
        return response.data[0]['id']
    except Exception as e:
        st.error(f"Fehler beim Erstellen der Analyse: {str(e)}")
        return None

def update_analysis(analysis_id, data):
    try:
        supabase = init_supabase()
        supabase.table('analyses').update(data).eq('id', analysis_id).execute()
        return True
    except Exception as e:
        st.error(f"Fehler beim Update der Analyse: {str(e)}")
        return False

def get_analysis(analysis_id):
    try:
        supabase = init_supabase()
        response = supabase.table('analyses').select('*').eq('id', analysis_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        st.error(f"Fehler beim Laden der Analyse: {str(e)}")
        return None

def main():
    st.title("Interview Analyzer")
    
    login()
    
    if st.session_state.get('authenticated', False):
        if st.session_state.get('current_project'):
            if st.session_state.get('view_analysis'):
                show_analysis_detail()
            else:
                show_project_overview()

def show_project_overview():
    st.markdown(f"""
        ### 🎯 Projekt: {st.session_state.current_project}
        ---
    """)
    
    col1, col2 = st.columns([3, 1])
    
    with col2:
        if st.button("➕ Neue Analyse", type="primary", use_container_width=True):
            st.session_state.show_upload_modal = True
    
    with col1:
        analyses = get_project_analyses(st.session_state.current_project)
        if analyses:
            st.markdown("### 📊 Analysen")
            
            # Verbesserte Tabelle mit Status
            df = pd.DataFrame([{
                "Nr.": idx + 1,
                "Datum": datetime.fromisoformat(a['created_at']).strftime('%d.%m.%Y %H:%M'),
                "Status": "✅ Fertig" if a['status'] == 'completed' else "⏳ In Bearbeitung",
                "Details": "Öffnen"
            } for idx, a in enumerate(analyses)])
            
            st.dataframe(
                df,
                column_config={
                    "Nr.": st.column_config.NumberColumn(width=50),
                    "Datum": st.column_config.TextColumn(width=150),
                    "Status": st.column_config.TextColumn(width=120),
                    "Details": st.column_config.ButtonColumn(width=100)
                },
                hide_index=True
            )

    # Upload Modal
    if st.session_state.get('show_upload_modal', False):
        modal = st.container()
        with modal:
            st.markdown("### 🎥 Neue Analyse")
            uploaded_file = st.file_uploader(
                "Video hochladen (MP4, MOV, AVI)", 
                type=['mp4', 'mov', 'avi']
            )
            
            col1, col2 = st.columns([1,1])
            with col1:
                start_disabled = not uploaded_file
                if st.button("🚀 Analyse starten", disabled=start_disabled, type="primary"):
                    if uploaded_file:
                        file_hash = hash(uploaded_file.getvalue())
                        analysis_id = create_analysis(st.session_state.current_project_id, file_hash)
                        
                        if analysis_id:
                            # Speichere File für Background Processing
                            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
                                tmp_file.write(uploaded_file.getvalue())
                                st.session_state.processing_file = tmp_file.name
                                st.session_state.processing_analysis_id = analysis_id
                            
                            st.session_state.show_upload_modal = False
                            st.rerun()
            
            with col2:
                if st.button("❌ Abbrechen"):
                    st.session_state.show_upload_modal = False
                    st.rerun()

def show_analysis_detail():
    analysis = get_analysis(st.session_state.current_analysis_id)
    
    st.markdown(f"""
        ### 🔍 Analyse Details
        _{datetime.fromisoformat(analysis['created_at']).strftime('%d.%m.%Y %H:%M')}_
        ---
    """)
    
    if analysis['status'] == 'pending':
        st.markdown("""
            <div style='text-align: center; padding: 2rem;'>
                <div class="stSpinner">
                    <div class="st-spinner-border" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                </div>
                <h3>Analyse wird durchgeführt...</h3>
                <p>Dies kann einige Minuten dauern. Bitte haben Sie Geduld.</p>
            </div>
        """, unsafe_allow_html=True)
        
        # Rotating status messages
        status_messages = [
            "Transkribiere Video...",
            "Analysiere Gespräch...",
            "Erstelle Zusammenfassung...",
            "Identifiziere Kernpunkte..."
        ]
        
        placeholder = st.empty()
        time.sleep(2)  # Prevent too frequent updates
        placeholder.info(random.choice(status_messages))
        
        st.rerun()  # Check status again
    
    else:
        col1, col2 = st.columns([1,4])
        with col1:
            if st.button("← Zurück"):
                st.session_state.view_analysis = False
                st.rerun()
        
        with st.expander("📝 Transkription", expanded=False):
            st.text_area("", analysis['transcript'], height=200)
        
        with st.expander("🔍 Analyse", expanded=True):
            st.markdown(analysis['analysis'])

# Background Processing
if 'processing_file' in st.session_state:
    video_path = st.session_state.processing_file
    analysis_id = st.session_state.processing_analysis_id
    
    try:
        # Transcription
        transcript = transcribe_video(video_path)
        if transcript:
            update_analysis(analysis_id, {
                'transcript': transcript,
                'status': 'transcribed'
            })
        
        # Analysis
        analysis = analyze_transcript(transcript)
        if analysis:
            update_analysis(analysis_id, {
                'analysis': analysis,
                'status': 'completed'
            })
        
        # Cleanup
        os.unlink(video_path)
        del st.session_state.processing_file
        del st.session_state.processing_analysis_id
    
    except Exception as e:
        st.error(f"Fehler bei der Verarbeitung: {str(e)}")
        if os.path.exists(video_path):
            os.unlink(video_path)

if __name__ == "__main__":
    main()