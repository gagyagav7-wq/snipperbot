import google.generativeai as genai
import json
import os

# Init sekali di level module
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
    MODEL = genai.GenerativeModel('gemini-1.5-flash')
else:
    MODEL = None

def ask_ai_judge(signal_type, bot_reason, metrics):
    if not MODEL: return {"decision": "REJECT", "reason": "AI Key Missing"}

    # Kasih konteks yang "kenyang" sesuai saran pro
    prompt = f"""
    As Senior XAUUSD Trader, debate this {signal_type} signal.
    Reason: {bot_reason}
    Market Context: {json.dumps(metrics)}
    
    Rules:
    - Reject if spread is high or feed is laggy.
    - Check if price is too close to PDH/PDL.
    Output JSON ONLY:
    {{"decision": "APPROVE/REJECT", "confidence": 0-100, "reason": "..."}}
    """

    try:
        response = MODEL.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return json.loads(response.text)
    except:
        return {"decision": "REJECT", "reason": "AI Error Fallback"}
