# ... (Import sama kayak sebelumnya)

print(f"🚀 BOT SCALPING 1M-5M-15M DIMULAI...")

while True:
    try:
        # Ambil Data
        data_dict = get_market_data(SYMBOL)
        if data_dict is None:
            time.sleep(10) # Retry cepet kalau gagal
            continue
            
        # Analisa
        analysis = analyze_technicals(data_dict)
        current_time = analysis['timestamp']
        
        # Cek apakah candle 1 menit baru close?
        if last_processed_time == current_time:
            time.sleep(5) # Cek tiap 5 detik biar presisi
            continue
            
        # Log Heartbeat per menit
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 1M Close: {analysis['price']} | 15M Trend: {analysis['trend_15m']} | Trig: {analysis['has_trigger']}")
        
        if analysis['has_trigger']:
            print("⚡ 1M Setup Detected! Checking with Council...")
            debate = run_debate(analysis)
            
            if debate:
                send_alert(debate, analysis)
                last_processed_time = current_time
        
        else:
            last_processed_time = current_time

        time.sleep(5)

    except Exception as e:
        print(f"Error: {e}")
        time.sleep(10)
