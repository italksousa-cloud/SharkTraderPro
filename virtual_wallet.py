import json
import os
from datetime import datetime
from logger_setup import logger
import plotly.graph_objects as go
import uuid

class VirtualWallet:
    def __init__(self, initial_balance, currency="USDT"):
        self.initial_balance = float(initial_balance)
        self.current_balance = float(initial_balance)
        self.in_position_balance = 0.0
        self.total_balance = float(initial_balance)
        self.currency = currency
        
        self.trade_history = []
        self.open_trades = {}
        self.equity_curve = [{"time": datetime.now().isoformat(), "balance": self.total_balance}]
        self.peak_balance = float(initial_balance)
        
        # Default stake settings
        self.stake_mode = "percentage"
        self.stake_percentage = 2.0
        self.stake_fixed = 50.0
        self.min_stake = 10.0
        self.max_stake = 5000.0
        self.max_open_trades = 3

    def set_stake(self, mode, value):
        if mode not in ["percentage", "fixed"]:
            raise ValueError("Stake mode must be 'percentage' or 'fixed'")
        self.stake_mode = mode
        if mode == "percentage":
            self.stake_percentage = float(value)
        else:
            self.stake_fixed = float(value)
        logger.info(f"Wallet stake set to {mode}: {value}")

    def calculate_stake(self):
        if self.stake_mode == "percentage":
            stake = self.current_balance * (self.stake_percentage / 100.0)
        else:
            stake = self.stake_fixed
            
        stake = max(self.min_stake, min(stake, self.max_stake))
        
        if stake > self.current_balance:
            logger.warning(f"Insufficient funds for stake {stake}. Available: {self.current_balance}")
            return 0.0
        return stake

    def open_trade(self, symbol, side, entry_price, quantity, stop_loss, take_profit):
        if len(self.open_trades) >= self.max_open_trades:
            logger.warning("Max open trades limit reached. Cannot open new trade.")
            return None
            
        cost = entry_price * quantity
        if cost > self.current_balance:
            logger.warning(f"Cannot open trade. Cost {cost} > Balance {self.current_balance}")
            return None
            
        fee = cost * 0.001 # 0.1% binance fee
        total_deduction = cost + fee
        
        if total_deduction > self.current_balance:
            return None
            
        self.current_balance -= total_deduction
        self.in_position_balance += cost
        self.total_balance = self.current_balance + self.in_position_balance
        
        trade_id = str(uuid.uuid4())[:8]
        
        trade = {
            "id": trade_id,
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "quantity": quantity,
            "cost": cost,
            "fee_entry": fee,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "entry_time": datetime.now().isoformat()
        }
        
        self.open_trades[trade_id] = trade
        logger.info(f"Wallet: Opened {side} {symbol} @ {entry_price}. ID: {trade_id}")
        return trade_id

    def close_trade(self, trade_id, exit_price):
        if trade_id not in self.open_trades:
            return None
            
        trade = self.open_trades.pop(trade_id)
        revenue = exit_price * trade["quantity"]
        fee_exit = revenue * 0.001
        
        if trade["side"] == "buy":
            gross_profit = revenue - trade["cost"]
        else:
            # Short simulation logic: we gain if exit < entry
            gross_profit = trade["cost"] - revenue
            
        net_profit = gross_profit - trade["fee_entry"] - fee_exit
        
        # Return cost to balance, add net profit
        self.in_position_balance -= trade["cost"]
        self.current_balance += (trade["cost"] + net_profit)
        self.total_balance = self.current_balance + self.in_position_balance
        
        if self.total_balance > self.peak_balance:
            self.peak_balance = self.total_balance
            
        self.equity_curve.append({
            "time": datetime.now().isoformat(),
            "balance": self.total_balance
        })
        
        trade["exit_price"] = exit_price
        trade["fee_exit"] = fee_exit
        trade["net_profit"] = net_profit
        trade["profit_pct"] = (net_profit / trade["cost"]) * 100 if trade["cost"]>0 else 0
        trade["exit_time"] = datetime.now().isoformat()
        trade["result"] = "win" if net_profit > 0 else "loss"
        
        self.trade_history.append(trade)
        logger.info(f"Wallet: Closed {trade['side']} {trade['symbol']} @ {exit_price}. PnL: ${net_profit:.2f}")
        return trade

    def get_open_trades(self):
        return list(self.open_trades.values())

    def get_balance(self):
        # Update total balance based on current market value would require live prices,
        # Here we return the static total based on entry cost. The Simulator handles live PnL.
        return {
            "available": self.current_balance,
            "in_position": self.in_position_balance,
            "total": self.total_balance,
            "profit_total": self.total_balance - self.initial_balance
        }

    def get_pnl(self):
        return self.total_balance - self.initial_balance

    def get_pnl_percentage(self):
        return (self.get_pnl() / self.initial_balance) * 100

    def get_drawdown(self):
        if self.peak_balance <= 0: return 0.0, 0.0
        current_dd = (self.peak_balance - self.total_balance) / self.peak_balance * 100
        
        # Max historical drawdown
        max_dd = 0.0
        peak = self.initial_balance
        for point in self.equity_curve:
            bal = point["balance"]
            if bal > peak: peak = bal
            dd = (peak - bal) / peak * 100
            if dd > max_dd: max_dd = dd
            
        return current_dd, max_dd

    def get_daily_pnl(self):
        today = datetime.now().date().isoformat()
        daily_pnl = sum([t["net_profit"] for t in self.trade_history if t["exit_time"].startswith(today)])
        return daily_pnl

    def get_equity_curve(self):
        return self.equity_curve

    def get_stats(self):
        total_trades = len(self.trade_history)
        if total_trades == 0:
            return {"total_trades": 0}
            
        wins = [t for t in self.trade_history if t["result"] == "win"]
        losses = [t for t in self.trade_history if t["result"] == "loss"]
        win_rate = (len(wins) / total_trades) * 100
        
        gross_profit = sum([t["net_profit"] for t in wins])
        gross_loss = abs(sum([t["net_profit"] for t in losses]))
        
        avg_profit = gross_profit / len(wins) if wins else 0
        avg_loss = gross_loss / len(losses) if losses else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        max_dd = self.get_drawdown()[1]
        best_trade = max([t["net_profit"] for t in self.trade_history]) if self.trade_history else 0
        worst_trade = min([t["net_profit"] for t in self.trade_history]) if self.trade_history else 0
        
        return {
            "total_trades": total_trades,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate,
            "avg_profit": avg_profit,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "max_drawdown": max_dd,
            "best_trade": best_trade,
            "worst_trade": worst_trade,
            "total_return_pct": self.get_pnl_percentage()
        }

    def check_risk_limits(self):
        curr_dd, max_dd = self.get_drawdown()
        if curr_dd >= 15.0:  # Hardcoded max DD threshold for wallet pause
            logger.error(f"Wallet risk limit: Drawdown {curr_dd:.2f}% exceeded 15% limit.")
            return False
            
        # Add basic logic to stop opening if daily loss > 5%
        daily_loss_pct = abs(min(0, self.get_daily_pnl())) / self.total_balance * 100
        if daily_loss_pct >= 5.0:
            logger.error(f"Wallet risk limit: Daily loss {daily_loss_pct:.2f}% exceeded 5% limit.")
            return False
            
        return True

    def reset(self):
        self.__init__(self.initial_balance, self.currency)

    def to_dict(self):
        return {
            "initial_balance": self.initial_balance,
            "current_balance": self.current_balance,
            "in_position_balance": self.in_position_balance,
            "total_balance": self.total_balance,
            "currency": self.currency,
            "equity_curve": self.equity_curve,
            "stake_mode": self.stake_mode,
            "stake_percentage": self.stake_percentage,
            "stake_fixed": self.stake_fixed
        }

    def save_state(self, path="wallet_state.json"):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=4)
            
    def load_state(self, path="wallet_state.json"):
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
                self.initial_balance = data["initial_balance"]
                self.current_balance = data["current_balance"]
                self.in_position_balance = data["in_position_balance"]
                self.total_balance = data["total_balance"]
                self.currency = data.get("currency", "USDT")
                self.equity_curve = data.get("equity_curve", [])
                self.stake_mode = data.get("stake_mode", "percentage")
                self.stake_percentage = data.get("stake_percentage", 2.0)
                self.stake_fixed = data.get("stake_fixed", 50.0)

    def print_summary(self):
        stats = self.get_stats()
        pnl = self.get_pnl()
        pnl_pct = self.get_pnl_percentage()
        sign = "+" if pnl >= 0 else ""
        
        print("\n" + "┌" + "─" * 37 + "┐")
        print(f"│       SHARK TRADER - BANCA VIRTUAL  │")
        print("├" + "─" * 37 + "┤")
        print(f"│ Banca Inicial:    ${self.initial_balance:,.2f}         │")
        print(f"│ Banca Atual:      ${self.current_balance:,.2f}         │")
        print(f"│ Em Operação:      ${self.in_position_balance:,.2f}            │")
        print(f"│ Lucro Total:      {sign}${abs(pnl):,.2f} ({sign}{pnl_pct:.1f}%) │")
        if stats.get('total_trades', 0) > 0:
            print(f"│ Trades: {stats['total_trades']:<2} | Win: {stats['win_rate']:>2.0f}% | DD: {stats['max_drawdown']:>3.1f}%   │")
        else:
            print(f"│ Trades: 0  | Win: 0%  | DD: 0.0%    │")
        print("└" + "─" * 37 + "┘\n")
