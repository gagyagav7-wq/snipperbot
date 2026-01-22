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

    # Extract Structure Data
    m15_struct = metrics.get('m15_structure', [])
    trend = metrics.get('trend_m15', 'NEUTRAL')

    prompt = f"""
    Role: Senior XAUUSD Scalper (SMC & Elliott Wave).
    
    Signal: {signal_type}
    Reason: {bot_reason}
    M15 Trend: {trend}
    
    Recent M15 Structure (Pivots): 
    {json.dumps(m15_struct, indent=2)}
    
    Task: Validate Trade Context.
    
    ELLIOTT WAVE RULES:
    1. Check Pivot Labels (HH, HL, LH, LL).
       - BUY SIGNAL requires a sequence of Higher Highs (HH) or Higher Lows (HL).
       - SELL SIGNAL requires Lower Lows (LL) or Lower Highs (LH).
    2. Identify Phase:
       - If price is making HH/HL -> Impulse Phase (Good for Buy).
       - If price is making LH/LL -> Correction/Down Trend (Bad for Buy).
    
    DECISION LOGIC:
    - APPROVE if structure aligns with signal direction (e.g. Buy on HL).
    - REJECT if signal fights the structure (e.g. Buy after a clear LH & LL sequence).
    
    Output JSON ONLY:
    {{
      "decision": "APPROVE" or "REJECT",
      "confidence": 0-100,
      "reason": "Explain structure (e.g. 'Valid buy on HL formation')",
      "wave_bias": "Impulse/Correction"
    }}
    """

    try:
        response = MODEL.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        text = response.text
        match = re.search(r'\{.*\}', text, re.DOTALL)
        return json.loads(match.group()) if match else json.loads(text)
    except:
        return {"decision": "REJECT", "reason": "AI Error"}
