import google.generativeai as genai
import json
import os

def ask_ai_judge(signal_type, bot_reason, metrics):
    # Setup API Key (Pastikan ada di .env)
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel('gemini-1.5-flash')

    prompt = f"""
    Kamu adalah Senior Trader XAUUSD.
    Bot mendeteksi sinyal {signal_type} karena: {bot_reason}
    Data Indikator: {json.dumps(metrics)}
    
    Tugas: Berikan debat singkat. Putuskan APPROVE atau REJECT.
    OUTPUT WAJIB JSON:
    {{"decision": "APPROVE", "confidence": 90, "reason": "alasan"}}
    """

    try:
        # Gunakan mode JSON
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"⚠️ AI Offline: {e}")
        # Fallback: Tolak sinyal jika AI error (lebih aman)
        return {"decision": "REJECT", "confidence": 0, "reason": "AI Error/Offline"}
