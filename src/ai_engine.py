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

    # (Update Prompt Only)

    prompt = f"""
    Role: Senior XAUUSD Scalper (SMC & Elliott Wave).
    
    Signal: {signal_type}
    Reason: {bot_reason}
    M15 Trend: {trend}
    
    Recent M15 Structure (Pivots): 
    {json.dumps(m15_struct, indent=2)}
    
    Task: Validate Trade Context.
    
    DEFINITIONS:
    - HH (Higher High) / LH (Lower High) -> Applies to Pivot type 'High'.
    - HL (Higher Low) / LL (Lower Low) -> Applies to Pivot type 'Low'.
    
    ELLIOTT WAVE RULES:
    1. Trend Confirmation:
       - BUY SIGNAL: Requires HL or HH sequence. Ideally buying a HL.
       - SELL SIGNAL: Requires LH or LL sequence. Ideally selling a LH.
    2. Phase Check:
       - If recent structure is LH + LL -> Down Trend Impulse. Risky to Buy.
       - If recent structure is HH + HL -> Up Trend Impulse. Risky to Sell.
    
    Output JSON ONLY:
    {{
      "decision": "APPROVE" or "REJECT",
      "confidence": 0-100,
      "reason": "Explain structure alignment",
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
