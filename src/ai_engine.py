import google.generativeai as genai
import json
import os
import re

def ask_ai_judge(signal_type, bot_reason, metrics):
    """Hakim AI dengan pengaman ganda pada parsing JSON"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"decision": "REJECT", "confidence": 0, "reason": "API Key Missing"}

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # Ringkasan data agar hemat token & akurat
    prompt = f"""
    Analisa sinyal {signal_type} XAUUSD.
    Alasan Bot: {bot_reason}
    Metrik: {json.dumps(metrics)}
    
    Tugas: Debat sinyal ini secara kritis. Berikan keputusan APPROVE atau REJECT.
    Output WAJIB dalam format JSON:
    {{
      "decision": "APPROVE atau REJECT",
      "confidence": 0-100,
      "risk_flags": ["list risiko"],
      "reason": "debat singkat"
    }}
    """

    try:
        response = model.generate_content(
            prompt, 
            generation_config={"response_mime_type": "application/json"}
        )
        # Pengaman ganda: coba parse langsung, kalau gagal pakai regex
        try:
            return json.loads(response.text)
        except:
            match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise ValueError("JSON not found")
            
    except Exception as e:
        print(f"⚠️ AI Engine Error: {e}")
        return {"decision": "REJECT", "confidence": 0, "reason": "AI Fallback: Reject due to error"}
