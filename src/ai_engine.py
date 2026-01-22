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

    # --- 1. EXTRACT DATA DARI METRICS ---
    # Ambil data trend & struktur M15
    indicators = metrics.get('indicators', {})
    trend = indicators.get('trend_m15', 'NEUTRAL')
    
    m15_data = indicators.get('m15_structure', {})
    sequence = m15_data.get('sequence', 'N/A')

    # Ambil Warnings (Laporan dari Indicators.py soal Lag/Drift)
    warnings = metrics.get('warnings', [])
    warn_str = ", ".join(warnings) if warnings else "None"

    # --- 2. CONSTRUCT PROMPT ---
    prompt = f"""
    Role: Senior XAUUSD Scalper (SMC & Elliott Wave).
    
    Signal: {signal_type}
    Reason: {bot_reason}
    M15 Trend: {trend}
    
    M15 Structure Sequence: {sequence}
    (Format: Type(Label) -> Next Type(Label)... Chronological Order)
    
    System Warnings: {warn_str}
    (Note: If warnings contain 'Lag' or 'Drift', be stricter. If warnings imply high volatility, REJECT).
    
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

    # --- 3. CALL AI & PARSE ---
    try:
        response = MODEL.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        text = response.text
        # Pakai Regex buat bersihin kalau ada teks aneh di luar JSON
        match = re.search(r'\{.*\}', text, re.DOTALL)
        return json.loads(match.group()) if match else json.loads(text)
    except:
        # Fallback kalau AI error/timeout
        return {"decision": "REJECT", "reason": "AI Error"}
