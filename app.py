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

        # Prüfe, ob ffmpeg verfügbar ist
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        except subprocess.CalledProcessError:
            st.error("FFmpeg ist nicht korrekt installiert.")
            return None

        # Konvertiere Video zu Audio
        audio_path = tmp_path + '.wav'
        try:
            subprocess.run([
                'ffmpeg', '-i', tmp_path,
                '-vn', 
                '-acodec', 'pcm_s16le',
                '-ar', '16000',
                '-ac', '1',
                audio_path
            ], capture_output=True, check=True)
        except subprocess.CalledProcessError as e:
            st.error(f"Fehler bei der Audio-Konvertierung: {e.stderr.decode()}")
            return None

        # Transkribiere Audio
        with st.spinner('Transkribiere Audio...'):
            result = model.transcribe(audio_path)

        # Cleanup
        os.unlink(tmp_path)
        os.unlink(audio_path)

        return result["text"]

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
            with st.spinner("Video wird transkribiert..."):
                transcript = transcribe_video(uploaded_file)
                st.subheader("Transkription:")
                st.text_area("", transcript, height=200)

            with st.spinner("Analyse wird durchgeführt..."):
                summary = summarize_with_gpt(transcript)
                st.subheader("Zusammenfassung der wichtigsten Punkte:")
                st.markdown(summary)

if __name__ == "__main__":
    main() 