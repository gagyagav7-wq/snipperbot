import google.generativeai as genai
import json
import re # Regex buat nyari JSON
from src.config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def extract_json(text):
    # Cari teks di antara kurung kurawal terluar { ... }
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return match.group(0)
    return text

def run_debate(setup_data, history_ctx):
    # Prompt yang lebih galak
    prompt = f"""
    SYSTEM: You are a JSON-ONLY Trading Engine. Do NOT write conversational text.
    
    DATA:
    Action: {setup_data['action']} @ {setup_data['entry']}
    Spread: {setup_data.get('spread', 'N/A')}
    Historical PDH: {history_ctx['daily']['pdh']} (If buying near here, REJECT)
    Historical PDL: {history_ctx['daily']['pdl']} (If selling near here, REJECT)

    AGENTS:
    1. 🐺 SNIPER: Wants to trade.
    2. 🛡️ RISK: Rejects if spread > 25, or trading into PDH/PDL support/resistance.
    3. ⚖️ REFEREE: Final verdict.

    OUTPUT FORMAT (JSON):
    {{
        "bull_score": 0-100,
        "bear_score": 0-100,
        "risk_status": "PASS" or "FAIL",
        "risk_reason": "Reason",
        "decision": "TRADE" or "SKIP",
        "summary": ["Point 1", "Point 2", "Point 3"]
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        raw_text = response.text
        
        # 1. Bersihin Markdown
        clean_text = raw_text.replace("```json", "").replace("```", "").strip()
        
        # 2. Extract JSON murni (kalau ada teks pembuka/penutup)
        json_str = extract_json(clean_text)
        
        return json.loads(json_str)
    except Exception as e:
        print(f"⚠️ AI Parse Error: {e} | Raw: {raw_text[:50]}...")
        return None
