import google.generativeai as genai
import json
from src.config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def run_debate(market_data):
    # Susun data jadi string
    pattern_str = ", ".join(market_data['patterns']) if market_data['patterns'] else "None"
    
    prompt = f"""
    ROLE: High-Frequency Trading Council for XAUUSD (Gold) M15.
    
    MARKET DATA:
    - Price: {market_data['price']:.2f}
    - RSI: {market_data['rsi']:.2f}
    - ATR: {market_data['atr']:.2f}
    - Patterns: {pattern_str}
    - M15 Trend: {market_data['m15_trend']}
    - H1 Trend (Major): {market_data['h1_trend']}
    - DXY (USD) Trend: {market_data['dxy_trend']} (Negative correlation with Gold)

    AGENTS:
    1. 🐺 SNIPER (Bull/Bear): Aggressive. Loves Engulfing/FVG patterns. Wants to trade NOW.
    2. 🛡️ RISK MANAGER: Conservative. Hates trading against H1 Trend or DXY Trend. Checks RSI.
    3. ⚖️ REFEREE: Final decision maker.

    TASK:
    Simulate a debate. If DXY Trend is BULLISH, Gold usually falls (Risk Manager should warn Sniper about buying).
    
    OUTPUT FORMAT (JSON ONLY):
    {{
        "sniper_opinion": "Short aggressive argument...",
        "risk_opinion": "Cautious argument regarding DXY/Trend...",
        "decision": "BUY" or "SELL" or "SKIP",
        "reason": "Final summary by Referee",
        "stop_loss": "Suggested price",
        "take_profit": "Suggested price"
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        # Bersihkan Markdown ```json
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except Exception as e:
        print(f"❌ AI Error: {e}")
        return None
