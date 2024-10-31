import streamlit as st
import whisper
import openai
import tempfile
import os
from pathlib import Path
import subprocess
import torch

# OpenAI API Key aus den Umgebungsvariablen oder Streamlit Secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Lade das Whisper-Modell beim Start
@st.cache_resource
def load_whisper_model():
    # Prüfe CUDA-Verfügbarkeit
    device = "cuda" if torch.cuda.is_available() else "cpu"
    st.info(f"Nutze Device: {device}")
    return whisper.load_model("base").to(device)

def transcribe_video(uploaded_file):
    try:
        # Erstelle einen Fortschrittsbalken
        progress_text = "Verarbeite Video..."
        progress_bar = st.progress(0, text=progress_text)
        
        # Debug-Information
        st.info(f"Verarbeite Datei: {uploaded_file.name} ({uploaded_file.size} bytes)")
        progress_bar.progress(10, "Erstelle temporäre Dateien...")
        
        # Erstelle temporäre Datei
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_video:
            tmp_video.write(uploaded_file.getvalue())
            video_path = tmp_video.name
        
        # Erstelle Audio-Pfad
        audio_path = video_path + '.wav'
        
        # FFmpeg-Befehl
        progress_bar.progress(20, "Konvertiere Audio...")
        command = [
            'ffmpeg',
            '-i', video_path,
            '-vn',
            '-acodec', 'pcm_s16le',
            '-ar', '16000',
            '-ac', '1',
            '-f', 'wav',
            audio_path
        ]
        
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode != 0:
            st.error(f"FFmpeg Fehler: {result.stderr}")
            return None
            
        progress_bar.progress(40, "Audio-Konvertierung abgeschlossen...")
        st.info(f"Audio-Datei erstellt: {os.path.getsize(audio_path)} bytes")
        
        # Lade Modell
        progress_bar.progress(50, "Lade Whisper Modell...")
        model = load_whisper_model()
        
        # Teile die Transkription in Segmente
        progress_bar.progress(60, "Starte Transkription (dies kann einige Minuten dauern)...")
        
        # Transkribiere mit optimierten Parametern
        transcription = model.transcribe(
            audio_path,
            fp16=False,
            language='de',
            initial_prompt="Dies ist ein User Interview auf Deutsch.",
            condition_on_previous_text=True,
            verbose=True
        )
        
        # Cleanup
        progress_bar.progress(90, "Räume auf...")
        os.unlink(video_path)
        os.unlink(audio_path)
        
        if not transcription or not transcription.get("text"):
            st.error("Keine Transkription erzeugt")
            return None
            
        progress_bar.progress(100, "Fertig!")
        return transcription["text"]
        
    except Exception as e:
        st.error(f"Fehler bei der Verarbeitung: {str(e)}")
        import traceback
        st.error(f"Stacktrace: {traceback.format_exc()}")
        return None
    finally:
        # Cleanup im Fehlerfall
        try:
            if 'video_path' in locals() and os.path.exists(video_path):
                os.unlink(video_path)
            if 'audio_path' in locals() and os.path.exists(audio_path):
                os.unlink(audio_path)
        except Exception:
            pass

def summarize_with_gpt(transcript):
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": """Du bist ein erfahrener UX Researcher und Experte für die Analyse von User Interviews. 
                Analysiere das Interview detailliert und strukturiere deine Erkenntnisse in folgende Kategorien:

                1. Haupterkenntnisse
                   - Zentrale Aussagen und Kernthemen
                   - Wichtige Zitate
                   - Überraschende Einsichten

                2. Nutzerverhalten & Bedürfnisse
                   - Aktuelle Verhaltensweisen
                   - Schmerzpunkte und Frustrationen
                   - Wünsche und Bedürfnisse
                   - Motivationen

                3. Kontext & Rahmenbedingungen
                   - Nutzungskontext
                   - Externe Einflüsse
                   - Technische Voraussetzungen

                4. Detaillierte Problembereiche
                   - Spezifische Herausforderungen
                   - Häufigkeit der Probleme
                   - Auswirkungen auf den Nutzer

                5. Konkrete Empfehlungen
                   - Kurzfristige Maßnahmen
                   - Langfristige Verbesserungen
                   - Priorisierte Handlungsempfehlungen
                   - Potenzielle Lösungsansätze

                Formatiere die Ausgabe übersichtlich mit Markdown."""
            },
            {
                "role": "user",
                "content": f"Hier ist die Transkription eines User Interviews. Bitte analysiere es entsprechend der vorgegebenen Struktur:\n\n{transcript}"
            }
        ],
        temperature=0.7
    )
    return response.choices[0].message.content

def main():
    st.title("User Interview Analyse Tool")
    
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