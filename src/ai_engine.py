import google.generativeai as genai
import json
import os
import re

MODEL = None

def init_ai():
    global MODEL
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        genai.configure(api_key=api_key)
        MODEL = genai.GenerativeModel('gemini-1.5-flash')

def ask_ai_judge(signal_type, bot_reason, metrics):
    if MODEL is None: init_ai()
    if MODEL is None: return {"decision": "REJECT", "reason": "AI Config Error"}

    # Prompt Khusus Scalping XAUUSD (SMC + EW Bias)
    prompt = f"""
    Role: Professional XAUUSD Scalper (SMC & Elliott Wave Expert).
    
    Signal: {signal_type}
    Reason: {bot_reason}
    Metrics: {json.dumps(metrics)}
    
    Task: Validate this scalping setup (Target 30-50 pips).
    
    Checklist:
    1. Trend Context: Is the trade aligned with the immediate momentum?
    2. Elliott Wave Bias: Does this look like a risky corrective wave (Wave 2/4/B)? If yes, REJECT.
    3. Price Action: Is there a clear rejection/reaction?
    
    Output JSON ONLY:
    {{
      "decision": "APPROVE" or "REJECT",
      "confidence": 0-100,
      "reason": "Technical reason in 10 words (e.g. 'Valid impulse wave 3, clear rejection')",
      "wave_bias": "Impulse/Correction/Unknown"
    }}
    """

    try:
        response = MODEL.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        text = response.text
        match = re.search(r'\{.*\}', text, re.DOTALL)
        return json.loads(match.group()) if match else json.loads(text)
    except:
        # Fallback aman: Kalau AI bingung, mending jangan trading
        return {"decision": "REJECT", "reason": "AI Error / Ambiguous Data"}
