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

    # Data Structure M15
    m15_data = metrics.get('m15_structure', {})
    rel_pos = m15_data.get('relative_pos', 0.5)

    # (Update Prompt ini)

    prompt = f"""
    Role: Senior SMC & Elliott Wave Strategist (XAUUSD Scalping).
    
    Signal: {signal_type}
    Reason: {bot_reason}
    Metrics: {json.dumps(metrics)}
    
    Context Data:
    - Recent Pivots (M15): {metrics.get('m15_pivots')}
    - Trend: {metrics.get('trend_m15')}
    
    Task: Validate Structure.
    
    ELLIOTT WAVE RULES:
    1. Read the 'm15_pivots'. 
       - If BUYING: Do we have a Higher High (HH) or Higher Low (HL) sequence? (Good)
       - If BUYING but pivots show Lower Highs (LH) + Lower Lows (LL): Counter-trend risk! (Reject/Caution)
       - If SELLING: Look for LH/LL sequence.
       
    2. Over-Extension Check:
       - If price is far above the last High pivot -> Buying Top Risk (Wave 5 end).
       
    DECISION:
    - APPROVE if structure supports the direction (Impulsive move).
    - REJECT if trying to catch a falling knife (Correction) without clear structure shift.
    
    Output JSON ONLY:
    {{
      "decision": "APPROVE" or "REJECT",
      "confidence": 0-100,
      "reason": "Explain wave structure based on pivots",
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
