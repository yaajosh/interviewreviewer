import streamlit as st
import whisper
import openai
import tempfile
import os
from pathlib import Path

# OpenAI API Key aus den Umgebungsvariablen oder Streamlit Secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]

def transcribe_video(video_file):
    # Temporäre Datei erstellen
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
        tmp_file.write(video_file.getvalue())
        tmp_path = tmp_file.name

    # Whisper Modell laden und Transkription durchführen
    model = whisper.load_model("base")
    result = model.transcribe(tmp_path)
    
    # Temporäre Datei löschen
    os.unlink(tmp_path)
    
    return result["text"]

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