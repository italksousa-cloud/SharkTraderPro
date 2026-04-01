import os
import threading
import time
from flask import Flask, jsonify, render_template
from flask_cors import CORS

from database import DatabaseManager
from virtual_wallet import VirtualWallet
from simulator import TradingSimulator
import config

# Initialize Flask
app = Flask(__name__)
CORS(app)

# Global instances
db = DatabaseManager()
wallet = VirtualWallet(5000.0, "USDT")
wallet.set_stake('percentage', 2.0)
sim = None
sim_thread = None

# --- BACKGROUND TASK ---
def run_simulator_background():
    global sim
    import logging
    from exchange_manager import ExchangeManager
    from pattern_detector import PatternDetector
    from multi_timeframe import MultiTimeframeAnalyzer
    from ml_engine import MLEngine
    from risk_manager import RiskManager
    
    # We initialize these inside the thread to avoid context issues
    exchange = ExchangeManager()
    symbols = exchange.get_top_futures(limit=config.MAX_SYMBOLS)
    
    sim = TradingSimulator(wallet, db)
    # Patch the simulator components
    sim.exchange = exchange
    sim.pd = PatternDetector()
    sim.mtf = MultiTimeframeAnalyzer(sim.exchange, sim.pd)
    sim.ml = MLEngine()
    sim.risk = RiskManager(db)
    
    # Prevent stdout spam in web mode, let it run quietly
    sim.print_live_status = lambda msg: None
    
    sim.start("live_paper", symbols, config.TIMEFRAMES)

def start_bot_thread():
    global sim_thread
    if sim_thread is None or not sim_thread.is_alive():
        sim_thread = threading.Thread(target=run_simulator_background, daemon=True)
        sim_thread.start()

# --- ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def status():
    is_running = sim.running if sim else False
    is_paused = sim.paused if sim else False
    return jsonify({
        "running": is_running,
        "paused": is_paused,
        "max_symbols": config.MAX_SYMBOLS
    })

@app.route('/api/wallet')
def wallet_api():
    stats = wallet.get_stats()
    balance_info = wallet.get_balance()
    return jsonify({
        "initial": wallet.initial_balance,
        "current": balance_info['total'],
        "available": balance_info['available'],
        "in_position": balance_info['in_position'],
        "pnl_pct": wallet.get_pnl_percentage(),
        "win_rate": stats.get('win_rate', 0),
        "total_trades": stats.get('total_trades', 0),
        "drawdown": stats.get('max_drawdown', 0),
        "best_trade": stats.get('best_trade', 0),
        "worst_trade": stats.get('worst_trade', 0)
    })

@app.route('/api/trades/open')
def open_trades():
    trades = wallet.get_open_trades()
    return jsonify(trades)

@app.route('/api/trades/history')
def trade_history():
    history = wallet.trade_history[-20:] # Last 20 trades
    return jsonify(history)

@app.route('/api/chart')
def equity_curve():
    return jsonify(wallet.get_equity_curve())

@app.route('/api/toggle')
def toggle_bot():
    global sim
    if not sim:
        start_bot_thread()
        return jsonify({"status": "started"})
        
    if sim.running:
        if sim.paused:
            sim.resume()
            return jsonify({"status": "resumed"})
        else:
            sim.pause()
            return jsonify({"status": "paused"})
    else:
        start_bot_thread()
        return jsonify({"status": "started"})

def run_server():
    print("Iniciando Servidor Web do Shark Trader Pro...")
    print("Acesse http://127.0.0.1:5000 no seu navegador.")
    import webbrowser
    # Short delay to let Flask start
    threading.Timer(1.5, lambda: webbrowser.open('http://127.0.0.1:5000/')).start()
    # Start bot immediately at launch
    start_bot_thread()
    # Disable reloader to prevent creating two bot instances
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

if __name__ == '__main__':
    run_server()
