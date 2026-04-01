import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
from logger_setup import logger

class Backtester:
    def __init__(self, db_manager):
        self.db = db_manager
        self.initial_balance = 1000.0
        self.balance = self.initial_balance
        self.trades = []
        self.equity_curve = [self.initial_balance]
        self.dates = []

    def simulate_trade(self, entry_date, entry_price, exit_date, exit_price, side, quantity, fee_pct=0.001):
        entry_cost = entry_price * quantity
        fee_entry = entry_cost * fee_pct
        
        exit_revenue = exit_price * quantity
        fee_exit = exit_revenue * fee_pct
        
        if side.lower() == 'buy':
            profit_loss = exit_revenue - entry_cost - fee_entry - fee_exit
        else: # Sell/Short
            profit_loss = entry_cost - exit_revenue - fee_entry - fee_exit
            
        profit_pct = (profit_loss / entry_cost) * 100 if entry_cost > 0 else 0
        
        self.balance += profit_loss
        self.equity_curve.append(self.balance)
        self.dates.append(exit_date)
        
        result = 'win' if profit_loss > 0 else ('loss' if profit_loss < 0 else 'breakeven')
        
        trade = {
            'symbol': 'SIM', 
            'side': side,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'quantity': quantity,
            'profit_loss': profit_loss,
            'profit_pct': profit_pct,
            'fee': fee_entry + fee_exit,
            'entry_time': entry_date,
            'exit_time': exit_date,
            'duration': str(pd.to_datetime(exit_date) - pd.to_datetime(entry_date)),
            'stop_loss': 0, 'take_profit': 0, 'timeframe': 'historical',
            'patterns_detected': [], 'ml_confidence': 0.0, 'ml_prediction': '',
            'confluence_score': 0.0, 'indicators_snapshot': {},
            'result': result,
            'is_backtest': 1,
            'notes': 'Backtest simulation'
        }
        self.trades.append(trade)
        return trade

    def save_all_to_db(self):
        saved = 0
        for t in self.trades:
            if self.db.save_trade(t):
                saved += 1
        logger.info(f"Saved {saved} backtest trades to database.")

    def run_dataframe(self, df, logic_func):
        """
        Runs a simulation over a DataFrame.
        `logic_func` is a callback that receives (index, row, current_balance, open_trades)
        and returns an action dict if a trade should be opened or closed.
        Very simplified structure.
        """
        logger.info("Starting DataFrame Backtest...")
        
        # This is a stub for the structure. A true vectorized backtester would be used here.
        # For Shark Trader Pro we will use the Simulator class in Part 5 for detailed live-feeling backtest.
        pass

    def generate_report(self):
        if not self.trades:
            logger.warning("No trades to report on.")
            return
            
        wins = len([t for t in self.trades if t['result'] == 'win'])
        losses = len([t for t in self.trades if t['result'] == 'loss'])
        win_rate = (wins / len(self.trades)) * 100
        
        gross_profit = sum([t['profit_loss'] for t in self.trades if t['profit_loss'] > 0])
        gross_loss = abs(sum([t['profit_loss'] for t in self.trades if t['profit_loss'] < 0]))
        pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        net_profit = sum([t['profit_loss'] for t in self.trades])
        total_return = (net_profit / self.initial_balance) * 100
        
        # Max drawdown
        peak = self.initial_balance
        max_dd = 0
        for b in self.equity_curve:
            if b > peak:
                peak = b
            dd = (peak - b) / peak * 100
            if dd > max_dd:
                max_dd = dd
                
        logger.info(f"--- BACKTEST REPORT ---")
        logger.info(f"Total Trades : {len(self.trades)}")
        logger.info(f"Win Rate     : {win_rate:.2f}% ({wins}W / {losses}L)")
        logger.info(f"Profit Factor: {pf:.2f}")
        logger.info(f"Net Profit   : ${net_profit:.2f} ({total_return:.2f}%)")
        logger.info(f"Max Drawdown : {max_dd:.2f}%")
        
        self._plot_equity()

    def _plot_equity(self):
        fig = go.Figure()
        
        x_data = self.dates if len(self.dates) == len(self.equity_curve) - 1 else list(range(len(self.equity_curve)))
        if len(x_data) < len(self.equity_curve):
            # Prepend start point
            if self.dates:
                x_data = [self.dates[0]] + self.dates
            else:
                x_data = list(range(len(self.equity_curve)))
                
        fig.add_trace(go.Scatter(x=x_data, y=self.equity_curve, mode='lines', name='Equity', line=dict(color='blue')))
        fig.update_layout(title="Backtest Equity Curve", xaxis_title="Time/Trades", yaxis_title="Balance ($)")
        
        try:
            fig.write_html("backtest_equity.html")
            logger.info("Saved equity curve to backtest_equity.html")
        except Exception as e:
            logger.error(f"Failed to plot equity curve: {e}")
