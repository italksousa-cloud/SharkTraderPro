import time
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
import os

from virtual_wallet import VirtualWallet
from database import DatabaseManager
from logger_setup import logger
from exchange_manager import ExchangeManager
from multi_timeframe import MultiTimeframeAnalyzer
from pattern_detector import PatternDetector
from ml_engine import MLEngine
from risk_manager import RiskManager
import utils
import config

class TradingSimulator:
    def __init__(self, wallet: VirtualWallet, db: DatabaseManager):
        self.wallet = wallet
        self.db = db
        self.paused = False
        self.running = False
        
        self.exchange = ExchangeManager()
        self.pd = PatternDetector()
        self.mtf = MultiTimeframeAnalyzer(self.exchange, self.pd)
        self.ml = MLEngine()
        self.risk = RiskManager(self.db)

    def start(self, mode, symbols, timeframes):
        self.running = True
        if mode == "live_paper":
            self.run_live_paper(symbols)
        elif mode == "historical":
            logger.info("Historical mode not fully detailed in prompt, running live_paper logic wrapper for demonstration.")
            self.run_live_paper(symbols) # Fallback to live_paper for now
            
    def pause(self):
        self.paused = True
        logger.info("Simulation paused.")
        
    def resume(self):
        self.paused = False
        logger.info("Simulation resumed.")
        
    def stop(self):
        self.running = False
        logger.info("Simulation stopped.")
        self.generate_final_report()

    def check_stops(self, current_prices):
        """Checks Stop Loss and Take Profit for all open trades in the virtual wallet."""
        closed_any = False
        for trade in list(self.wallet.get_open_trades()):
            symbol = trade["symbol"]
            if symbol not in current_prices:
                continue
                
            curr_price = current_prices[symbol]
            side = trade["side"]
            sl = trade["stop_loss"]
            tp = trade["take_profit"]
            
            should_close = False
            if side == "buy":
                if curr_price <= sl or curr_price >= tp:
                    should_close = True
            elif side == "sell":
                if curr_price >= sl or curr_price <= tp:
                    should_close = True
                    
            if should_close:
                closed_trade = self.wallet.close_trade(trade["id"], curr_price)
                closed_trade["is_backtest"] = 1 # Mark as simulated/paper
                self.db.save_trade(closed_trade)
                closed_any = True
                
        return closed_any

    def print_live_status(self, last_signal="None"):
        os.system("cls" if os.name == "nt" else "clear")
        stats = self.wallet.get_stats()
        b_init = self.wallet.initial_balance
        b_curr = self.wallet.total_balance
        pnl_pct = self.wallet.get_pnl_percentage()
        sign = "+" if pnl_pct >= 0 else ""
        
        print("┌" + "─" * 46 + "┐")
        print("│  🦈 SHARK TRADER PRO - SIMULAÇÃO             │")
        print(f"│  Banca: ${b_init:,.2f} → ${b_curr:,.2f} ({sign}{pnl_pct:.1f}%)       │")
        if stats.get('total_trades', 0) > 0:
            print(f"│  Trades: {stats['total_trades']:<2} | Wins: {stats['wins']:<2} | Losses: {stats['losses']:<2} | WR: {stats['win_rate']:.0f}% │")
            print(f"│  Drawdown: {stats['max_drawdown']:.1f}% | Melhor: ${stats['best_trade']:.0f} | Pior: ${stats['worst_trade']:.0f}  │")
        else:
            print("│  Trades: 0  | Wins: 0  | Losses: 0  | WR: 0% │")
            print("│  Drawdown: 0.0% | Melhor: $0 | Pior: $0    │")
            
        stake_val = self.wallet.calculate_stake()
        if self.wallet.stake_mode == "percentage":
            print(f"│  Stake: {self.wallet.stake_percentage}% (${stake_val:,.2f} por trade)               │")
        else:
            print(f"│  Stake: Fixo (${stake_val:,.2f} por trade)               │")
            
        print("│  " + "─" * 42 + " │")
        print(f"│  Último: {last_signal:<37}│")
        
        opens = self.wallet.get_open_trades()
        if opens:
            # Pegamos o primeiro pra mostrar
            t = opens[0]
            # Estimativa de PnL (precisaria do preço atual, usando 0 aqui pro display simples)
            print(f"│  Abertos: {t['symbol']} {t['side'].upper()} @ ${t['entry_price']:.2f} (1/{len(opens)})          │")
        else:
            print("│  Abertos: Nenhum                               │")
        print("└" + "─" * 46 + "┘")

    def run_live_paper(self, symbols):
        logger.info("Starting LIVE PAPER simulation loop. Press Ctrl+C to stop.")
        last_signal_text = "Nenhum sinal ainda"
        
        try:
            while self.running:
                if self.paused:
                    time.sleep(1)
                    continue
                    
                if not self.wallet.check_risk_limits():
                    logger.warning("Wallet risk limits reached (DD or Daily Loss). Pausing simulation.")
                    self.pause()
                    continue

                current_prices = {}
                
                # Update prices and check stops
                for sym in symbols:
                    ticker = self.exchange.get_ticker(sym)
                    if ticker and 'last' in ticker:
                        current_prices[sym] = ticker['last']
                
                if self.check_stops(current_prices):
                    self.print_live_status(last_signal_text)
                
                # Scan for new signals
                for symbol in symbols:
                    if len(self.wallet.get_open_trades()) >= self.wallet.max_open_trades:
                        break # Max trades reached
                        
                    analysis = self.mtf.analyze(symbol)
                    if abs(analysis['confluence_score']) > 15:
                        df_snap = self.exchange.get_ohlcv(symbol, '1d', limit=50)
                        df_snap = utils.calculate_indicators(df_snap)
                        if df_snap is None or df_snap.empty: continue
                        snap = df_snap.iloc[-1]
                        
                        features = {
                            'confluence_score': analysis['raw_confluence'],
                            'rsi': snap.get('rsi', 50),
                            'macd': snap.get('macd', 0),
                            'atr': snap.get('atr', 0),
                            'close': snap.get('close', 0),
                            'bollinger_upper': snap.get('bollinger_upper', 0),
                            'bollinger_lower': snap.get('bollinger_lower', 0)
                        }
                        
                        confidence = self.ml.predict(features)
                        
                        if confidence >= config.ML_CONFIDENCE_THRESHOLD:
                            # 1. Price
                            price = current_prices.get(symbol, snap['close'])
                            side = "buy" if analysis['direction'] == 'bullish' else "sell"
                            
                            # 2. Risk check
                            sl, tp = self.risk.calculate_dynamic_stops(price, features['atr'], side)
                            stake_cash = self.wallet.calculate_stake()
                            
                            if stake_cash > 0:
                                qty = stake_cash / price
                                trade_id = self.wallet.open_trade(symbol, side, price, qty, sl, tp)
                                if trade_id:
                                    last_signal_text = f"{symbol} {side.upper()} conf:{confidence:.2f} ✅"
                                    self.print_live_status(last_signal_text)
                                    
                self.print_live_status(last_signal_text)
                time.sleep(15) # Refresh interval
                
        except KeyboardInterrupt:
            self.stop()

    def generate_final_report(self):
        logger.info("Generating Final Simulation Report...")
        curve = self.wallet.get_equity_curve()
        if len(curve) > 1:
            df = pd.DataFrame(curve)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df.index, y=df['balance'], mode='lines', name='Balance'))
            fig.update_layout(title="Simulator Equity Curve", yaxis_title="USD")
            fig.write_html("simulate_equity.html")
            logger.info("Saved simulate_equity.html")
        else:
            logger.warning("No trades were executed to plot.")
            
        self.wallet.print_summary()
