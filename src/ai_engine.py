import google.generativeai as genai
import json

# Ganti pakai API Key lu, Bre!
genai.configure(api_key="API_KEY_GEMINI_LU")

def ask_ai_judge(signal_type, bot_reason, market_data):
    """Hakim AI yang memberikan keputusan dalam format JSON ketat"""
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # Ringkasan data (Saran GPT: Jangan kirim sampah data)
    summary = {
        "rsi": market_data.get("rsi"),
        "adx": market_data.get("adx"),
        "trend_m15": market_data.get("ema_trend"),
        "dist_pdl_pts": market_data.get("dist_pdl_pts"),
        "dist_pdh_pts": market_data.get("dist_pdh_pts")
    }

    prompt = f"""
    Analisa sinyal {signal_type} XAUUSD.
    Alasan Bot: {bot_reason}
    Data Indikator: {json.dumps(summary)}
    
    Debatlah sinyal ini. Jika sangat berisiko, REJECT. Jika konfirmasi kuat, APPROVE.
    WAJIB JAWAB DALAM JSON:
    {{"decision": "APPROVE/REJECT", "confidence": 0-100, "reason": "alasan singkat"}}
    """

    try:
        # Pake JSON Mode
        response = model.generate_content(
            prompt, 
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"⚠️ AI Error: {e}")
        # Fallback (Saran GPT: Kalau error, jangan biarkan bot mati)
        return {"decision": "REJECT", "confidence": 0, "reason": "AI Offline/Error"}
