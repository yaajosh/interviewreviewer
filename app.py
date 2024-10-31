import streamlit as st
import whisper
import openai
import tempfile
import os
from pathlib import Path
import subprocess

# OpenAI API Key aus den Umgebungsvariablen oder Streamlit Secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Lade das Whisper-Modell beim Start
@st.cache_resource  # Cache das Modell zwischen Runs
def load_whisper_model():
    return whisper.load_model("base")

# Initialisiere das Modell
model = load_whisper_model()

def transcribe_video(uploaded_file):
    try:
        # Erstelle temporäre Datei mit korrekter Dateierweiterung
        suffix = os.path.splitext(uploaded_file.name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name

        # Konvertiere Video zu Audio mit verbesserten Parametern
        audio_path = tmp_path + '.wav'
        try:
            # Prüfe zuerst die Eingabedatei
            probe_command = [
                'ffmpeg',
                '-i', tmp_path,
                '-hide_banner'
            ]
            probe_result = subprocess.run(
                probe_command,
                capture_output=True,
                text=True
            )
            
            # Konvertiere zu Audio
            command = [
                'ffmpeg',
                '-i', tmp_path,
                '-vn',                # Keine Video-Ausgabe
                '-acodec', 'pcm_s16le', # Audio-Codec
                '-ar', '16000',       # Sample rate
                '-ac', '1',           # Mono
                '-f', 'wav',          # Format erzwingen
                '-y',                 # Überschreibe Ausgabedatei
                audio_path
            ]
            
            # Führe Konvertierung aus
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Prüfe die Ausgabedatei
            if not os.path.exists(audio_path):
                st.error("Audiodatei wurde nicht erstellt")
                return None
                
            if os.path.getsize(audio_path) < 1024:  # Kleiner als 1KB
                st.error("Audiodatei ist zu klein oder leer")
                return None
                
            # Versuche die Audio-Datei zu lesen
            with open(audio_path, 'rb') as audio_file:
                audio_data = audio_file.read()
                if len(audio_data) < 1024:
                    st.error("Audio-Daten sind zu klein")
                    return None

            # Transkribiere Audio
            st.info("Starte Transkription...")
            result = model.transcribe(audio_path)
            
            if not result or not result.get("text"):
                st.error("Keine Transkription erzeugt")
                return None
                
            return result["text"]

        except subprocess.CalledProcessError as e:
            st.error(f"Fehler bei der Audio-Konvertierung: {e.stderr}")
            return None
        finally:
            # Cleanup
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                if os.path.exists(audio_path):
                    os.unlink(audio_path)
            except Exception as e:
                st.warning(f"Cleanup-Fehler: {str(e)}")

    except Exception as e:
        st.error(f"Fehler bei der Verarbeitung: {str(e)}")
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