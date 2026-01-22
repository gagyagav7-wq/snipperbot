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

    # (Bagian Prompt di src/ai_engine.py update jadi gini)

    prompt = f"""
    Role: SMC & Elliott Wave Scalper (XAUUSD).
    
    Signal: {signal_type}
    Reason: {bot_reason}
    Metrics: {json.dumps(metrics)}
    
    Data Context:
    - Trend M15: {metrics.get('trend_m15')}
    - M15 Structure: {json.dumps(metrics.get('m15_structure'))}
    
    Task: Validate Setup (SL $3-$5).
    1. Elliott Wave Check: Compare 'current_price' with 'm15_structure'. 
       - If buying near M15 High -> Risk of Wave 5 ending / Wave B correction.
       - If selling near M15 Low -> Risk of Wave 5 ending.
    2. Trend & Momentum: Confirm trend alignment.
    
    Output JSON ONLY:
    {{
      "decision": "APPROVE" or "REJECT",
      "confidence": 0-100,
      "reason": "Technical rationale",
      "wave_bias": "Impulse/Correction"
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
