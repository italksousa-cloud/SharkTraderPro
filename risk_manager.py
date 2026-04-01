from logger_setup import logger
import config

class RiskManager:
    def __init__(self, db_manager):
        self.db = db_manager
        self.max_risk_pct = config.RISK_PER_TRADE_PCT / 100.0
        self.tp_ratio_1 = config.TAKE_PROFIT_RATIO_1
        self.tp_ratio_2 = config.TAKE_PROFIT_RATIO_2
        self.max_simultaneous = config.MAX_SIMULTANEOUS_TRADES
        self.max_daily_loss = config.MAX_DAILY_LOSS_PCT / 100.0
        self.max_drawdown = config.MAX_DRAWDOWN_PCT / 100.0

    def calculate_position_size(self, balance, entry_price, stop_loss_price):
        """
        Calculates how much asset to buy based on the risk percentage of the total balance.
        """
        risk_amount = balance * self.max_risk_pct
        price_diff = abs(entry_price - stop_loss_price)
        
        if price_diff <= 0:
            return 0
            
        qty = risk_amount / price_diff
        # Ensure we don't buy more than we can afford (no margin used here purely spot/1x style logic)
        max_qty_by_balance = balance / entry_price
        
        actual_qty = min(qty, max_qty_by_balance)
        return float(actual_qty)

    def calculate_dynamic_stops(self, entry_price, atr, side):
        """
        Calculates Stop Loss and Take Profit based on ATR dynamically.
        ATR multiplier: 1.5x for SL
        """
        sl_dist = atr * 1.5
        
        if side.lower() == 'buy':
            stop_loss = entry_price - sl_dist
            take_profit = entry_price + (sl_dist * self.tp_ratio_1) # 1:2 risk/reward based on ATR
        else: # sell/short
            stop_loss = entry_price + sl_dist
            take_profit = entry_price - (sl_dist * self.tp_ratio_1)
            
        return float(stop_loss), float(take_profit)

    def calculate_trailing_stop(self, current_price, current_sl, atr, side, activation_profit_pct=0.01):
        """
        Returns new Stop Loss if trailing is activated and price moved favorably.
        """
        # Simplistic approach: Keep SL at distance `atr * 1.5` from current highest/lowest price
        sl_dist = atr * 1.5
        new_sl = current_sl
        
        if side.lower() == 'buy':
            potential_sl = current_price - sl_dist
            if potential_sl > current_sl:
                new_sl = potential_sl
        else:
            potential_sl = current_price + sl_dist
            if potential_sl < current_sl:
                new_sl = potential_sl
                
        return float(new_sl)

    def can_open_trade(self, current_open_count, current_balance, start_of_day_balance):
        """
        Checks global risk constraints limits.
        """
        if current_open_count >= self.max_simultaneous:
            logger.warning(f"Risk Block: Already at max simultaneous trades ({self.max_simultaneous}).")
            return False
            
        # Daily loss limit check
        if start_of_day_balance > 0:
            daily_loss_pct = (start_of_day_balance - current_balance) / start_of_day_balance
            if daily_loss_pct >= self.max_daily_loss:
                logger.warning(f"Risk Block: Daily loss limit reached ({daily_loss_pct*100:.2f}% / {self.max_daily_loss*100:.2f}%).")
                return False
                
        return True
