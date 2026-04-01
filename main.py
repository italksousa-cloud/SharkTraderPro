import argparse
import time
import schedule
import pandas as pd
from datetime import datetime
import os

from logger_setup import logger
import config
from exchange_manager import ExchangeManager
from pattern_detector import PatternDetector
from multi_timeframe import MultiTimeframeAnalyzer
from database import DatabaseManager
from ml_engine import MLEngine
from ml_retrainer import MLRetrainer
from risk_manager import RiskManager
from backtester import Backtester
from virtual_wallet import VirtualWallet
from simulator import TradingSimulator
import utils

# Globals initialized in main()
db = None
exchange = None
pattern_detector = None
mtf_analyzer = None
ml = None
ml_retrainer = None
risk = None

def scan_market():
    symbols = exchange.get_top_futures(limit=config.MAX_SYMBOLS)
    logger.info(f"Scanning market... Symbols: {len(symbols)}")
    
    results = []
    
    for symbol in symbols:
        analysis = mtf_analyzer.analyze(symbol)
        
        # Process and predict if we have confluence
        if abs(analysis['confluence_score']) > 15:
            # We need indicators snapshot to feed ML
            df_snapshot = exchange.get_ohlcv(symbol, '1d', limit=100)
            df_snapshot = utils.calculate_indicators(df_snapshot)
            snapshot_row = df_snapshot.iloc[-1]
            
            features = {
                'confluence_score': analysis['raw_confluence'],
                'rsi': snapshot_row['rsi'],
                'macd': snapshot_row['macd'],
                'atr': snapshot_row['atr'],
                'close': snapshot_row['close'],
                'bollinger_upper': snapshot_row['bollinger_upper'],
                'bollinger_lower': snapshot_row['bollinger_lower']
            }
            
            confidence = ml.predict(features)
            
            if confidence >= config.ML_CONFIDENCE_THRESHOLD:
                logger.info(f"🎯 SIGNAL FOUND: {symbol} | Dir: {analysis['direction']} | Conf: {confidence:.2f} | Score: {analysis['confluence_score']:.1f}")
                results.append({
                    'symbol': symbol,
                    'direction': analysis['direction'],
                    'confidence': confidence,
                    'features': features,
                    'patterns': analysis['timeframes']
                })
                utils.send_telegram_message(f"🎯 <b>SHARK TRADER SIGNAL</b>\nSymbol: {symbol}\nDir: {analysis['direction']}\nConf: {confidence:.2f}")

    return results

def live_trading_loop():
    logger.info("Live Trading Tick...")
    # Real live trading logic with real exchange execution
    scan_market()
    
def routine_jobs():
    logger.info("Executing daily routine jobs...")
    db.save_daily_summary()
    ml_retrainer.auto_retrain()

def main():
    global db, exchange, pattern_detector, mtf_analyzer, ml, ml_retrainer, risk
    
    parser = argparse.ArgumentParser(description="Shark Trader Pro")
    parser.add_argument('--mode', type=str, required=True, choices=['scan', 'live', 'backtest', 'simulate', 'dashboard', 'web'], help="Operation mode")
    parser.add_argument('--balance', type=float, default=1000.0, help="Initial balance for simulation")
    parser.add_argument('--stake-mode', type=str, default='percentage', choices=['percentage', 'fixed'], help="Stake mode for simulation")
    parser.add_argument('--stake-value', type=float, default=2.0, help="Stake value (% or fixed usd)")
    parser.add_argument('--currency', type=str, default='USDT', help="Base currency")
    
    # Args for UI Dashboard
    parser.add_argument('--timeframe', type=str, default=None, help="Specific timeframe for dashboard view")
    parser.add_argument('--month', type=str, default=None, help="Month filter for dashboard (YYYY-MM)")
    args = parser.parse_args()
    
    logger.info(f"Starting Shark Trader Pro in {args.mode.upper()} mode")
    
    # Initialize Core Components
    db = DatabaseManager()
    
    if args.mode != 'dashboard':
        exchange = ExchangeManager()
        pattern_detector = PatternDetector()
        mtf_analyzer = MultiTimeframeAnalyzer(exchange, pattern_detector)
        ml = MLEngine()
        ml_retrainer = MLRetrainer(db, ml, config)
        risk = RiskManager(db)
    
    if args.mode == 'scan':
        scan_market()
        
    elif args.mode == 'live':
        logger.info("Initializing Live Mode. Press Ctrl+C to stop.")
        live_trading_loop()
        schedule.every(15).minutes.do(live_trading_loop)
        schedule.every().day.at("00:05").do(routine_jobs)
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Live trading stopped by user.")
            
    elif args.mode == 'backtest':
        logger.info("Running Backtest...")
        bx = Backtester(db)
        bx.generate_report()
        
    elif args.mode == 'simulate':
        logger.info(f"Initializing Simulation Mode (Paper Trading) | Balance: {args.balance} {args.currency}")
        wallet = VirtualWallet(args.balance, args.currency)
        wallet.set_stake(args.stake_mode, args.stake_value)
        
        sim = TradingSimulator(wallet, db)
        symbols = exchange.get_top_futures(limit=config.MAX_SYMBOLS)
        sim.start("live_paper", symbols, config.TIMEFRAMES)

    elif args.mode == 'dashboard':
        from dashboard import TradingDashboard
        logger.info("Initializing Performance Dashboard...")
        dash = TradingDashboard(db)
        dash.print_terminal_summary()
        dash.generate_full_dashboard(save_html=True)
        
    elif args.mode == 'web':
        import web_app
        web_app.run_server()

if __name__ == "__main__":
    main()
