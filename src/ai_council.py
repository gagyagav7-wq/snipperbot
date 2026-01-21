import google.generativeai as genai
import json
from src.config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def run_debate(data, historical_ctx): # Tambah parameter historical_ctx
    
    # Format data sejarah jadi string ringkas
    hist_str = f"""
    - YESTERDAY: Trend {historical_ctx['daily']['trend']}, High {historical_ctx['daily']['pdh']}, Low {historical_ctx['daily']['pdl']}
    - LAST WEEK: Trend {historical_ctx['weekly']['trend']}, Range {historical_ctx['weekly']['range_low']} - {historical_ctx['weekly']['range_high']}
    - LAST MONTH: Range {historical_ctx['monthly']['range_low']} - {historical_ctx['monthly']['range_high']}
    """
    
    prompt = f"""
    ROLE: Elite Gold (XAUUSD) Scalping Council.
    
    CONTEXT (HISTORICAL ANALYSIS):
    {hist_str}
    
    CURRENT MARKET (1M/5M/15M):
    - Price: {data['price']:.2f}
    - 1M Pattern: {", ".join(data['patterns']) if data['patterns'] else "None"}
    - 15M Trend: {data['trend_15m']}
    - DXY Trend: {data['dxy_trend']}

    AGENTS:
    1. 🐺 SNIPER: Wants to trade based on 1M patterns.
    2. 🧠 STRATEGIST: Checks Historical Levels.
       (CRITICAL: If Price is near Yesterday's High or Weekly High, DO NOT BUY -> Resistance!)
       (CRITICAL: If Price is near Yesterday's Low or Weekly Low, DO NOT SELL -> Support!)
    3. 🛡️ RISK MANAGER: Watches DXY and Spread.
    4. ⚖️ REFEREE: Final Decision.

    TASK: Decide based on Multi-Timeframe logic + Historical Levels.
    
    OUTPUT JSON:
    {{
        "sniper_opinion": "...",
        "strategist_opinion": "...",
        "risk_opinion": "...",
        "decision": "BUY" or "SELL" or "SKIP",
        "reason": "...",
        "stop_loss": "...",
        "take_profit": "..."
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except:
        return None
