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

    # Extract Data (Defensive)
    trend = metrics.get('trend_m15', 'NEUTRAL')
    m15_struct = metrics.get('m15_structure') 
    if not m15_struct:
        m15_struct = metrics.get('indicators', {}).get('m15_structure', {})
        
    sequence = m15_struct.get('sequence', 'N/A')
    last_pivot = m15_struct.get('last_pivot', 'N/A')
    dist_to_pivot = m15_struct.get('dist_to_pivot', 0.0)
    leg_sizes = m15_struct.get('leg_sizes', []) # Ambil Data Leg Sizes

    warnings = metrics.get('warnings', [])
    warn_str = ", ".join(warnings) if warnings else "None"

    # PROMPT V14: Leg Size Integrated
    prompt = f"""
    Role: Senior XAUUSD Scalper (SMC & ZigZag Wave Analyst).
    
    Signal: {signal_type}
    Reason: {bot_reason}
    M15 Trend: {trend}
    
    M15 Structure (ZigZag): {sequence}
    Recent Leg Sizes: {leg_sizes} (Volatility Proxy)
    Last Pivot: {last_pivot}
    Distance to Pivot: ${dist_to_pivot:.2f}
    
    System Warnings: {warn_str}
    
    Task: Validate Trade Context.
    
    RULES:
    1. TREND ALIGNMENT:
       - BUY: Structure should imply Higher Lows (HL) or Higher Highs (HH).
       - SELL: Structure should imply Lower Highs (LH) or Lower Lows (LL).
       
    2. WAVE & MOMENTUM (Leg Analysis):
       - Strong Impulse = Large leg sizes in trend direction.
       - Corrective pullback = Small leg sizes.
       - Avoid trading if legs are tiny (Choppy/No Volatility).
       
    3. DON'T CHASE:
       - If BUYING and Distance to Pivot (HH) is tiny -> Risk of buying top.
       - If SELLING and Distance to Pivot (LL) is tiny -> Risk of selling bottom.
    
    DECISION:
    - APPROVE: Structure aligns, momentum exists (healthy legs), entry not chasing.
    - REJECT: Fighting structure or Low Volatility Chop.
    
    Output JSON ONLY:
    {{
      "decision": "APPROVE" or "REJECT",
      "confidence": 0-100,
      "reason": "Explain structure & momentum",
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
