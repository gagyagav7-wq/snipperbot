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

    # --- FIX 1: DATA PLUMBING (MATCH V9 RUN_BOT) ---
    # Karena di run_bot data 'indicators' sudah di-unpack,
    # kita bisa akses langsung dari root metrics.
    
    # Trend M15
    trend = metrics.get('trend_m15', 'NEUTRAL')
    
    # Structure (Sequence & Pivots)
    # Hati-hati: m15_structure bisa jadi ada di root ATAU di dalam 'indicators'
    # tergantung cara kirimnya. Kita cek dua-duanya biar aman (Defensive).
    m15_struct = metrics.get('m15_structure') 
    if not m15_struct:
        m15_struct = metrics.get('indicators', {}).get('m15_structure', {})
        
    sequence = m15_struct.get('sequence', 'N/A')

    # Warnings & Lag
    warnings = metrics.get('warnings', [])
    warn_str = ", ".join(warnings) if warnings else "None"

    # --- 2. PROMPT CONSTRUCTION ---
    prompt = f"""
    Role: Senior XAUUSD Scalper (SMC & Elliott Wave).
    
    Signal: {signal_type}
    Reason: {bot_reason}
    M15 Trend: {trend}
    
    M15 Structure Sequence: {sequence}
    (Format: Type(Label) -> Next Type(Label)... Chronological Order)
    
    System Warnings: {warn_str}
    (Note: If warnings contain 'Lag' or 'Drift', increase scrutiny. If high volatility implied, REJECT).
    
    Task: Validate Trade Context.
    
    STRUCTURE RULES (ELLIOTT WAVE PROXY):
    1. BUY SIGNAL: Look for "L(HL) -> H(HH)" or at least "L(HL)".
       - Reject if sequence shows "H(LH) -> L(LL)" (Downtrend Structure).
    2. SELL SIGNAL: Look for "H(LH) -> L(LL)" or at least "H(LH)".
       - Reject if sequence shows "L(HL) -> H(HH)" (Uptrend Structure).
    
    DECISION LOGIC:
    - APPROVE if structure sequence supports the trend direction.
    - REJECT if signal is fighting the sequence (e.g. Buying on a Lower Low).
    
    Output JSON ONLY:
    {{
      "decision": "APPROVE" or "REJECT",
      "confidence": 0-100,
      "reason": "Explain using structure sequence",
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
