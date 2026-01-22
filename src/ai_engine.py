import google.generativeai as genai
import json
import os
import re

# Load model sekali saja
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

    # Prompt Spesial Scalping SMC + Elliott Wave
    prompt = f"""
    Act as a World-Class XAUUSD Scalper specializing in Smart Money Concepts (SMC) and Elliott Wave Theory.
    
    Signal: {signal_type}
    Technical Reason: {bot_reason}
    Market Context: {json.dumps(metrics)}
    
    Your Task:
    1. SMC Check: Is the price reacting to a valid Order Block or FVG? (Check 'dist_ob' in metrics).
    2. Elliott Wave Check: Based on the 'trend' (EMA), are we likely in a corrective wave (risky) or impulsive wave (safe)?
    3. Scalping Risk: Reject if the setup seems to be against a strong higher timeframe momentum.
    
    Output JSON ONLY:
    {{
      "decision": "APPROVE" or "REJECT",
      "confidence": 0-100,
      "reason": "Explain using SMC terms (e.g., 'Valid retest of bullish OB', 'Counter-trend correction wave detected')",
      "wave_analysis": "Brief Elliott Wave bias (e.g., 'Wave 3 impulse probable')"
    }}
    """

    try:
        response = MODEL.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        text = response.text
        match = re.search(r'\{.*\}', text, re.DOTALL)
        return json.loads(match.group()) if match else json.loads(text)
    except:
        return {"decision": "REJECT", "reason": "AI Parsing Error"}
