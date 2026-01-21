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

    prompt = f"""
    As Senior Gold Trader, analyze {signal_type}. 
    Reason: {bot_reason}
    Context: {json.dumps(metrics)}
    
    Rules: Strictly provide JSON only.
    {{ "decision": "APPROVE/REJECT", "confidence": 0-100, "reason": "short debate", "risks": [] }}
    """

    try:
        response = MODEL.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        text = response.text
        # Regex fallback jika AI "nakal" kasih markdown
        match = re.search(r'\{.*\}', text, re.DOTALL)
        return json.loads(match.group()) if match else json.loads(text)
    except:
        return {"decision": "REJECT", "reason": "AI Parsing Error"}
