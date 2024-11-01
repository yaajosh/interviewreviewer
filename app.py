import streamlit as st
import tempfile
import os
from datetime import datetime
from supabase import create_client
import openai

# Whisper erst laden, wenn wirklich benötigt
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
    """Transkribiert ein Video mit Whisper"""
    try:
        model = load_whisper()
        if model is None:
            return None
            
        result = model.transcribe(video_path)
        return result["text"]
    except Exception as e:
        st.error(f"Fehler bei der Transkription: {str(e)}")
        return None

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
                transcript = transcribe_video(video_path)
                if transcript is None:
                    status_container.error("❌ Transkription fehlgeschlagen")
                    return
                
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
    st.set_page_config(
        page_title="Interview Analyzer",
        page_icon="🎯",
        layout="wide"
    )

    st.markdown("""
    <style>
        .stButton button {
            background-color: transparent;
            border: 1px solid #444;
            border-radius: 8px;
            transition: all 0.2s;
        }
        .stButton button:hover {
            border-color: #888;
            background-color: #333;
        }
        [data-testid="stSidebar"] {
            background-color: #1E1E1E;
        }
        .st-emotion-cache-1r4qj8v {  /* Modal Hintergrund */
            background-color: #1E1E1E;
        }
        .st-emotion-cache-1r4qj8v h1 {  /* Modal Titel */
            color: white;
        }
    </style>
    """, unsafe_allow_html=True)

    main()