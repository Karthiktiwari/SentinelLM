import os
import google.generativeai as genai
import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM") # Default to Rachel

# Configure Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def generate_anomaly_summary(anomaly_event):
    """
    Uses Gemini to generate a concise, urgent summary of the anomaly.
    """
    agent_name = anomaly_event.get('node_name') or anomaly_event.get('agent_id') or 'Unknown Agent'
    
    if not GEMINI_API_KEY:
        return f"Anomaly detected on agent {agent_name}."

    try:
        model = genai.GenerativeModel('gemini-3-flash-preview')
        
        prompt = f"""
        You are a security monitoring AI. An anomaly has been detected in an AI Agent system.
        Generate a very short, urgent, spoken-style alert summary (max 2 sentences) for a security dashboard.
        
        Anomaly Details:
        - Agent Node: {agent_name}
        - Type: {anomaly_event.get('anomaly_type', 'unknown')}
        - Tokens Used: {anomaly_event.get('total_tokens', 'unknown')}
        - Loop Count: {anomaly_event.get('loop_count', 'unknown')}
        
        The summary should sound professional but urgent.
        """
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Gemini Error: {e}")
        return f"Alert. Anomaly detected on agent {agent_name}."

def text_to_speech(text):
    """
    Uses ElevenLabs to convert text to speech. Returns audio bytes.
    """
    if not ELEVENLABS_API_KEY:
        print("ElevenLabs API Key missing")
        return None

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }
    
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.5
        }
    }
    
    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            return response.content
        else:
            print(f"ElevenLabs Error: {response.text}")
            return None
    except Exception as e:
        print(f"ElevenLabs Exception: {e}")
        return None
