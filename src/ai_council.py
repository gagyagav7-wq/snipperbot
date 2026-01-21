import google.generativeai as genai
import json
from src.config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def run_debate(data, history):
    # Gabungin data teknikal & sejarah jadi string padat
    context_str = f"""
    ASSET: XAUUSD (Gold)
    CURRENT PRICE: {data['price']:.2f}
    
    1. MARKET STRUCTURE (TIME FRAMES):
       - 1M (Micro): Pattern {", ".join(data['patterns']) if data['patterns'] else "None"}, Trend {data['trend_1m']}
       - 5M (Tactical): Trend {data['trend_5m']}, RSI {data['rsi_5m']:.1f}
       - 15M (Bias): Trend {data['trend_15m']}
       
    2. KEY LEVELS (HISTORICAL):
       - Prev Day High: {history['daily']['pdh']} | Low: {history['daily']['pdl']}
       - Weekly Range: {history['weekly']['range_low']} - {history['weekly']['range_high']}
       
    3. CORRELATION:
       - DXY (Dollar): Trend {data['dxy_trend']} (Negative correlation expected)
    """

    prompt = f"""
    ROLE: Elite Algorithmic Trading Council. You are NOT a chat assistant. You are a JSON generator for a trading engine.
    OBJECTIVE: Analyze the data and output a trading decision with strict numerical scoring.

    AGENTS:
    1. 🐺 SNIPER (Bull Score 0-100): Rates buying pressure based on Patterns & 1M/5M alignment.
    2. 🐻 BEAR (Bear Score 0-100): Rates selling pressure based on Resistance & DXY strength.
    3. 🛡️ RISK MANAGER (Status: SAFE/CAUTION/DANGER): Checks historical levels (Don't buy at resistance!) and DXY correlation.
    4. ⚖️ REFEREE: Final Decision based on (Bull Score - Bear Score) and Risk Status.

    LOGIC RULES:
    - IF Risk Status is "DANGER", Decision MUST be "SKIP".
    - IF DXY is Bullish, Gold Buy Score must be penalized.
    - IF Price is near Prev Day High, Buy Score must be penalized (Resistance).
    - RuleScore is the overall quality of the technical setup (0-100).

    OUTPUT FORMAT (STRICT JSON ONLY, NO TEXT):
    {{
        "decision": "BUY" or "SELL" or "SKIP",
        "scores": {{
            "rule_score": 0-100,
            "bull_score": 0-100,
            "bear_score": 0-100
        }},
        "risk": {{
            "status": "SAFE" or "CAUTION" or "DANGER",
            "reason": "Max 5 words explanation"
        }},
        "setup": {{
            "entry": {data['price']:.2f},
            "sl": "price",
            "tp": "price"
        }},
        "summary": [
            "Point 1: Sniper's main argument",
            "Point 2: Strategist's main concern/support",
            "Point 3: Risk Manager's verdict",
            "Point 4: Correlation check (DXY/MTF)"
        ]
    }}
    
    DATA TO ANALYZE:
    {context_str}
    """
    
    try:
        response = model.generate_content(prompt)
        # Bersihin output biar jadi murni JSON
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        print(f"❌ AI Brain Error: {e}")
        return None
