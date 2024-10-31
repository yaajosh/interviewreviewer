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
        # Debug-Information
        st.info(f"Verarbeite Datei: {uploaded_file.name} ({uploaded_file.size} bytes)")
        
        # Erstelle temporäre Datei
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_video:
            tmp_video.write(uploaded_file.getvalue())
            video_path = tmp_video.name
            
        # Erstelle Audio-Pfad
        audio_path = video_path + '.wav'
        
        # FFmpeg-Befehl mit Debug-Output
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
        
        st.info("Starte Audio-Konvertierung...")
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode != 0:
            st.error(f"FFmpeg Fehler: {result.stderr}")
            return None
            
        if not os.path.exists(audio_path):
            st.error("Audio-Datei wurde nicht erstellt")
            return None
            
        # Audio-Datei-Info
        st.info(f"Audio-Datei erstellt: {os.path.getsize(audio_path)} bytes")
        
        # Lade Modell neu
        model = load_whisper_model()
        
        # Transkribiere mit expliziten Parametern
        st.info("Starte Transkription...")
        transcription = model.transcribe(
            audio_path,
            fp16=False,  # Verwende float32
            language='de'  # Explizite Sprache
        )
        
        # Cleanup
        os.unlink(video_path)
        os.unlink(audio_path)
        
        if not transcription or not transcription.get("text"):
            st.error("Keine Transkription erzeugt")
            return None
            
        return transcription["text"]
        
    except Exception as e:
        st.error(f"Fehler bei der Verarbeitung: {str(e)}")
        import traceback
        st.error(f"Stacktrace: {traceback.format_exc()}")
        return None

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
    st.write("Laden Sie ein Video-Interview hoch, um es zu transkribieren und analysieren zu lassen.")

    uploaded_file = st.file_uploader("Wählen Sie eine Videodatei aus", type=['mp4', 'mov', 'avi'])

    if uploaded_file is not None:
        if st.button("Analysieren"):
            # Fortschrittsbalken
            progress_bar = st.progress(0, "Starte Analyse...")
            
            # Status-Container für detaillierte Updates
            with st.status("🎬 Verarbeite Interview...", expanded=True) as status:
                # Phase 1: Video-Konvertierung
                st.write("🎥 Konvertiere Video...")
                progress_bar.progress(20)
                
                # Phase 2: Transkription
                st.write("🎙️ Erstelle Transkription...")
                transcript = transcribe_video(uploaded_file)
                progress_bar.progress(60)
                
                if transcript:
                    # Phase 3: GPT Analyse
                    st.write("🧠 Analysiere Inhalt mit GPT-4...")
                    summary = summarize_with_gpt(transcript)
                    progress_bar.progress(90)
                    
                    # Phase 4: Fertigstellung
                    st.write("✨ Formatiere Ergebnisse...")
                    progress_bar.progress(100)
                    status.update(label="✅ Analyse abgeschlossen!", state="complete", expanded=False)

                    # Ergebnisse anzeigen
                    st.success("Analyse erfolgreich abgeschlossen!")
                    
                    with st.expander("📝 Transkription", expanded=True):
                        st.text_area("", transcript, height=200)

                    with st.expander("📊 Analyse", expanded=True):
                        st.markdown(summary)

                    # Erfolgsanimation
                    st.balloons()
                else:
                    status.update(label="❌ Fehler bei der Verarbeitung", state="error")
                    progress_bar.empty()

if __name__ == "__main__":
    main() 