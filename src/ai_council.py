import google.generativeai as genai
import json
from src.config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def run_debate(setup_data):
    # Setup data isinya entry, sl, tp, reason dari Rule Engine
    
    prompt = f"""
    ROLE: Algorithmic Trading Supervisor (XAUUSD Scalping).
    
    PROPOSED SETUP (FROM RULE ENGINE):
    - Action: {setup_data['action']}
    - Entry: {setup_data['entry']} | SL: {setup_data['sl']} | TP: {setup_data['tp']}
    - Technical Reason: {setup_data['reason']}
    - Volatility (ATR): {setup_data['atr']}
    
    AGENTS:
    1. 🐂 BULL AGENT & 🐻 BEAR AGENT: Debate the technical strength.
    2. 🛡️ RISK MANAGER: Checks if SL is too tight/wide based on ATR, or if setup looks like a liquidity trap.
    3. ⚖️ REFEREE: Final decision.
    
    CRITICAL RULES:
    - If Risk Manager Fails, Decision MUST be SKIP.
    - If (Bull Score - Bear Score) < 20, Decision is SKIP (Weak consensus).
    
    OUTPUT FORMAT (JSON ONLY):
    {{
        "bull_score": 0-100,
        "bear_score": 0-100,
        "risk_status": "PASS" or "FAIL",
        "risk_reason": "Short reason",
        "referee_decision": "TRADE" or "SKIP",
        "summary": "3 bullet points summary"
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except:
        return None
