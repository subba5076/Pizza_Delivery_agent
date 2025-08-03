import whisper
import tempfile
import os
import uuid

# Load Whisper model
model = whisper.load_model("base")

def speech_to_text(audio_path):
    """
    Transcribe audio file to text using Whisper
    """
    try:
        result = model.transcribe(audio_path)
        return result["text"]
    except Exception as e:
        print(f"Whisper transcription error: {e}")
        return ""