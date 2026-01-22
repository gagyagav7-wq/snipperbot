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

    trend = metrics.get('trend_m15', 'NEUTRAL')
    m15_struct = metrics.get('m15_structure') 
    if not m15_struct:
        m15_struct = metrics.get('indicators', {}).get('m15_structure', {})
        
    sequence = m15_struct.get('sequence', 'N/A')
    last_pivot = m15_struct.get('last_pivot', 'N/A')
    dist_to_pivot = m15_struct.get('dist_to_pivot', 0.0)
    leg_sizes = m15_struct.get('leg_sizes_signed', [])
    
    # FIX: Ambil Konteks OBS
    is_obs = m15_struct.get('last_pivot_is_obs', False)
    pivot_type = m15_struct.get('last_pivot_type', 'None')

    warnings = metrics.get('warnings', [])
    warn_str = ", ".join(warnings) if warnings else "None"

    # PROMPT V17: Liquidity Sweep Logic
    prompt = f"""
    Role: Senior XAUUSD Scalper (SMC & ZigZag Wave Analyst).
    
    Signal: {signal_type}
    Reason: {bot_reason}
    M15 Trend: {trend}
    
    M15 Structure (ZigZag): {sequence}
    Recent Leg Sizes (+Up/-Down): {leg_sizes} 
    Last Pivot: {last_pivot}
    Distance to Pivot: ${dist_to_pivot:.2f}
    
    System Warnings: {warn_str}
    
    Task: Validate Trade Context.
    
    RULES:
    1. TREND & WAVE:
       - BUY: Structure Higher Lows (HL). Legs (+) > Legs (-).
       - SELL: Structure Lower Highs (LH). Legs (-) > Legs (+).
       
    2. LIQUIDITY SWEEP (Outside Bar Logic):
       - Current Last Pivot is OBS: {is_obs} (Type: {pivot_type})
       - If Last Pivot is 'Low' & OBS = True -> Bullish Sweep (High prob BUY).
       - If Last Pivot is 'High' & OBS = True -> Bearish Sweep (High prob SELL).
       - If Signal BUY but Last Pivot is 'High' OBS -> Warning (Trading into sweep).
       
    3. DON'T CHASE:
       - Avoid buying right at the top of a large (+) leg.
    
    DECISION:
    - APPROVE: Structure aligns OR Valid Liquidity Sweep (OBS) in signal direction.
    - REJECT: Fighting structure, bad momentum, or clock drift warning.
    
    Output JSON ONLY:
    {{
      "decision": "APPROVE" or "REJECT",
      "confidence": 0-100,
      "reason": "Explain structure, momentum & OBS sweep",
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
