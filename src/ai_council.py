import google.generativeai as genai
import json
from src.config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def run_debate(data):
    pattern_str = ", ".join(data['patterns']) if data['patterns'] else "None"
    
    prompt = f"""
    ROLE: High-Frequency Scalping Council for Gold (XAUUSD).
    STRATEGY: Multi-Timeframe Waterfall (15m Trend -> 5m Confirmation -> 1m Entry).
    
    MARKET DATA:
    - Current Price: {data['price']:.2f}
    - 1M (Micro): RSI {data['rsi_1m']:.1f}, Trend {data['trend_1m']}, Pattern: {pattern_str}
    - 5M (Tactical): RSI {data['rsi_5m']:.1f}, Trend {data['trend_5m']}
    - 15M (Bias): Trend {data['trend_15m']} (DO NOT TRADE AGAINST THIS)
    - DXY (Correlation): Trend {data['dxy_trend']}

    AGENTS:
    1. 🐺 SNIPER (1M Specialist): Obsessed with the 1-minute chart patterns. Wants to enter NOW based on micro-movements.
    2. 🧠 STRATEGIST (15M/5M Logic): Checks if the 1M move aligns with the 15M trend. Hates false breakouts.
    3. 🛡️ RISK MANAGER: Checks RSI extremes and spread. Vetoes if DXY supports the opposite direction.
    4. ⚖️ REFEREE: Final Decision.

    TASK:
    Debate. If Sniper sees a signal but Strategist says it contradicts 15M trend, verdict must be SKIP.
    
    OUTPUT FORMAT (JSON ONLY):
    {{
        "sniper_opinion": "...",
        "strategist_opinion": "...",
        "risk_opinion": "...",
        "decision": "BUY" or "SELL" or "SKIP",
        "reason": "Final Verdict Summary",
        "stop_loss": "Suggested price (tight for 1m scalping)",
        "take_profit": "Suggested price"
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except Exception as e:
        return None
