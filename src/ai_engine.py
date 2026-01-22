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

    prompt = f"""
    Role: Senior SMC & Elliott Wave Strategist (XAUUSD Scalping).
    
    Signal: {signal_type}
    Reason: {bot_reason}
    Metrics: {json.dumps(metrics)}
    
    M15 Context (Relative Position): {rel_pos:.2f} (0.0=Low, 1.0=High)
    
    Task: Validate Trade Safety.
    
    ELLIOTT WAVE LOGIC:
    - If BUYING and Relative Position > 0.85: HIGH RISK (Likely Wave 5 top or Wave B correction). -> REJECT or CAUTION.
    - If SELLING and Relative Position < 0.15: HIGH RISK (Likely Wave 5 bottom). -> REJECT or CAUTION.
    - Ideally, we want to catch Wave 3 or Wave C in the middle of the range.
    
    DECISION RULES:
    1. REJECT if price is pushing extremes counter-trend (trying to buy the exact top).
    2. REJECT if spread is eating >15% of the projected profit (check metrics).
    3. APPROVE if retest is clean and room to move exists.
    
    Output JSON ONLY:
    {{
      "decision": "APPROVE" or "REJECT",
      "confidence": 0-100,
      "reason": "Brief tech analysis",
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
