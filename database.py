import sqlite3
import json
import pandas as pd
from datetime import datetime
from logger_setup import logger
import config

class DatabaseManager:
    def __init__(self, db_path=config.DB_PATH):
        self.db_path = db_path
        self._create_tables()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _create_tables(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # trades_history
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    side TEXT,
                    entry_price REAL,
                    exit_price REAL,
                    quantity REAL,
                    profit_loss REAL,
                    profit_pct REAL,
                    fee REAL,
                    entry_time TEXT,
                    exit_time TEXT,
                    duration TEXT,
                    stop_loss REAL,
                    take_profit REAL,
                    timeframe TEXT,
                    patterns_detected TEXT,
                    ml_confidence REAL,
                    ml_prediction TEXT,
                    confluence_score REAL,
                    indicators_snapshot TEXT,
                    result TEXT,
                    is_backtest INTEGER DEFAULT 0,
                    notes TEXT
                )
            ''')
            
            # patterns_performance
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS patterns_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_name TEXT,
                    timeframe TEXT,
                    symbol TEXT,
                    times_detected INTEGER DEFAULT 0,
                    times_correct INTEGER DEFAULT 0,
                    times_wrong INTEGER DEFAULT 0,
                    avg_profit REAL,
                    avg_loss REAL,
                    win_rate REAL,
                    best_market_condition TEXT,
                    last_updated TEXT,
                    UNIQUE(pattern_name, timeframe, symbol)
                )
            ''')
            
            # ml_training_log
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ml_training_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    model_version TEXT,
                    accuracy REAL,
                    precision_score REAL,
                    recall REAL,
                    f1_score REAL,
                    features_used TEXT,
                    feature_importance TEXT,
                    training_samples INTEGER,
                    validation_score REAL,
                    notes TEXT
                )
            ''')
            
            # market_snapshots
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS market_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    symbol TEXT,
                    timeframe TEXT,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    rsi REAL,
                    macd REAL,
                    bollinger_upper REAL,
                    bollinger_lower REAL,
                    atr REAL,
                    trend_direction TEXT,
                    patterns_active TEXT
                )
            ''')
            
            # daily_performance
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE,
                    total_trades INTEGER,
                    wins INTEGER,
                    losses INTEGER,
                    total_profit REAL,
                    total_loss REAL,
                    net_pnl REAL,
                    best_trade REAL,
                    worst_trade REAL,
                    max_drawdown REAL,
                    win_rate REAL
                )
            ''')
            conn.commit()
            logger.debug("Database initialized and tables verified.")

    def save_trade(self, trade_data: dict):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                keys = []
                values = []
                for k, v in trade_data.items():
                    keys.append(k)
                    if isinstance(v, dict) or isinstance(v, list):
                        values.append(json.dumps(v))
                    else:
                        values.append(v)
                
                placeholders = ', '.join(['?'] * len(keys))
                keys_str = ', '.join(keys)
                query = f"INSERT INTO trades_history ({keys_str}) VALUES ({placeholders})"
                
                cursor.execute(query, values)
                conn.commit()
                logger.info(f"Trade history saved for {trade_data.get('symbol')}")
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error saving trade: {e}")
            return None

    def get_trades(self, symbol=None, result=None, start_date=None, end_date=None, is_backtest=False):
        where_clauses = ["is_backtest = ?"]
        params = [1 if is_backtest else 0]

        if symbol:
            where_clauses.append("symbol = ?")
            params.append(symbol)
        if result:
            where_clauses.append("result = ?")
            params.append(result)
        if start_date:
            where_clauses.append("entry_time >= ?")
            params.append(start_date)
        if end_date:
            where_clauses.append("entry_time <= ?")
            params.append(end_date)
            
        where_sql = " AND ".join(where_clauses)
        query = f"SELECT * FROM trades_history WHERE {where_sql} ORDER BY entry_time DESC"
        
        with self._get_connection() as conn:
            return pd.read_sql_query(query, conn, params=params)

    def update_pattern_stats(self, pattern_name, timeframe, symbol, is_correct, profit):
        now = datetime.now().isoformat()
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Check if exists
                cursor.execute("SELECT * FROM patterns_performance WHERE pattern_name=? AND timeframe=? AND symbol=?", 
                             (pattern_name, timeframe, symbol))
                row = cursor.fetchone()
                
                if row:
                    # Update
                    id_ = row[0]
                    times_detected = row[4] + 1
                    times_correct = row[5] + (1 if is_correct else 0)
                    times_wrong = row[6] + (0 if is_correct else 1)
                    avg_profit = row[7]
                    avg_loss = row[8]
                    
                    if is_correct:
                        avg_profit = (avg_profit * row[5] + profit) / times_correct if times_correct > 0 else profit
                    else:
                        avg_loss = (avg_loss * row[6] + profit) / times_wrong if times_wrong > 0 else profit
                        
                    win_rate = (times_correct / times_detected) * 100
                    
                    cursor.execute('''
                        UPDATE patterns_performance
                        SET times_detected=?, times_correct=?, times_wrong=?, 
                            avg_profit=?, avg_loss=?, win_rate=?, last_updated=?
                        WHERE id=?
                    ''', (times_detected, times_correct, times_wrong, avg_profit, avg_loss, win_rate, now, id_))
                else:
                    # Insert
                    times_correct = 1 if is_correct else 0
                    times_wrong = 0 if is_correct else 1
                    avg_profit = profit if is_correct else 0.0
                    avg_loss = profit if not is_correct else 0.0
                    win_rate = 100.0 if is_correct else 0.0
                    
                    cursor.execute('''
                        INSERT INTO patterns_performance 
                        (pattern_name, timeframe, symbol, times_detected, times_correct, times_wrong, 
                         avg_profit, avg_loss, win_rate, last_updated)
                        VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
                    ''', (pattern_name, timeframe, symbol, times_correct, times_wrong, avg_profit, avg_loss, win_rate, now))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating pattern stats: {e}")

    def save_ml_training(self, metrics: dict):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO ml_training_log (timestamp, model_version, accuracy, precision_score, 
                                               recall, f1_score, features_used, feature_importance, 
                                               training_samples, validation_score, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    datetime.now().isoformat(),
                    metrics.get('model_version', 'v1.0'),
                    metrics.get('accuracy', 0.0),
                    metrics.get('precision_score', 0.0),
                    metrics.get('recall', 0.0),
                    metrics.get('f1_score', 0.0),
                    json.dumps(metrics.get('features_used', [])),
                    json.dumps(metrics.get('feature_importance', {})),
                    metrics.get('training_samples', 0),
                    metrics.get('validation_score', 0.0),
                    metrics.get('notes', '')
                ))
                conn.commit()
                logger.info("ML training metrics saved.")
        except Exception as e:
            logger.error(f"Error saving ML training metrics: {e}")

    def save_market_snapshot(self, data: dict):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO market_snapshots (timestamp, symbol, timeframe, open, high, low, close, 
                                                  volume, rsi, macd, bollinger_upper, bollinger_lower, 
                                                  atr, trend_direction, patterns_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    data.get('timestamp', datetime.now().isoformat()),
                    data.get('symbol'),
                    data.get('timeframe'),
                    data.get('open'),
                    data.get('high'),
                    data.get('low'),
                    data.get('close'),
                    data.get('volume'),
                    data.get('rsi'),
                    data.get('macd'),
                    data.get('bollinger_upper'),
                    data.get('bollinger_lower'),
                    data.get('atr'),
                    data.get('trend_direction'),
                    json.dumps(data.get('patterns_active', []))
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving market snapshot: {e}")

    def save_daily_summary(self, date=None):
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
            
        try:
            with self._get_connection() as conn:
                df = pd.read_sql_query("SELECT * FROM trades_history WHERE entry_time LIKE ?", conn, params=(f"{date}%",))
                if df.empty:
                    return
                
                total_trades = len(df)
                wins = len(df[df['result'] == 'win'])
                losses = len(df[df['result'] == 'loss'])
                total_profit = df[df['profit_loss'] > 0]['profit_loss'].sum()
                total_loss = df[df['profit_loss'] < 0]['profit_loss'].sum()
                net_pnl = df['profit_loss'].sum()
                best_trade = df['profit_loss'].max()
                worst_trade = df['profit_loss'].min()
                win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
                max_drawdown = 0 # simplified
                
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO daily_performance (date, total_trades, wins, losses, total_profit, 
                                                   total_loss, net_pnl, best_trade, worst_trade, 
                                                   max_drawdown, win_rate)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(date) DO UPDATE SET
                    total_trades=excluded.total_trades, wins=excluded.wins, losses=excluded.losses,
                    total_profit=excluded.total_profit, total_loss=excluded.total_loss, net_pnl=excluded.net_pnl,
                    best_trade=excluded.best_trade, worst_trade=excluded.worst_trade, 
                    max_drawdown=excluded.max_drawdown, win_rate=excluded.win_rate
                ''', (date, total_trades, wins, losses, total_profit, total_loss, net_pnl, best_trade, worst_trade, max_drawdown, win_rate))
                conn.commit()
                logger.info(f"Daily summary saved for {date}")
        except Exception as e:
            logger.error(f"Error saving daily summary: {e}")

    def get_ml_training_data(self, days=90):
        # Retorna trades e snapshots de indicadores para treinamento
        query = f"""
            SELECT t.result, t.side, t.patterns_detected, t.confluence_score,
                   s.rsi, s.macd, s.bollinger_upper, s.bollinger_lower, s.atr, s.trend_direction
            FROM trades_history t
            LEFT JOIN market_snapshots s ON t.symbol = s.symbol AND t.timeframe = s.timeframe AND t.entry_time >= s.timestamp
            WHERE t.entry_time >= date('now', '-{days} days')
            GROUP BY t.id
        """
        with self._get_connection() as conn:
            return pd.read_sql_query(query, conn)

    def get_pattern_win_rates(self):
        query = "SELECT pattern_name, timeframe, win_rate, times_detected FROM patterns_performance ORDER BY win_rate DESC"
        with self._get_connection() as conn:
            return pd.read_sql_query(query, conn)

    def get_best_conditions(self, pattern_name):
        query = "SELECT best_market_condition FROM patterns_performance WHERE pattern_name=?"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (pattern_name,))
            res = cursor.fetchone()
            return res[0] if res else None

    def get_total_trades_since_last_training(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT timestamp FROM ml_training_log ORDER BY id DESC LIMIT 1")
            last_training = cursor.fetchone()
            if last_training:
                cursor.execute("SELECT COUNT(*) FROM trades_history WHERE entry_time > ?", (last_training[0],))
                return cursor.fetchone()[0]
            else:
                cursor.execute("SELECT COUNT(*) FROM trades_history")
                return cursor.fetchone()[0]

    def export_to_csv(self, table_name, path):
        with self._get_connection() as conn:
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
            df.to_csv(path, index=False)
            logger.info(f"Table {table_name} exported to {path}")

    def get_dashboard_data(self):
        with self._get_connection() as conn:
            stats = {}
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*), SUM(profit_loss) FROM trades_history WHERE is_backtest=0")
            row = cursor.fetchone()
            stats['live_trades'] = row[0]
            stats['live_pnl'] = row[1] if row[1] else 0.0
            
            cursor.execute("SELECT COUNT(*), SUM(profit_loss) FROM trades_history WHERE is_backtest=1")
            row = cursor.fetchone()
            stats['backtest_trades'] = row[0]
            stats['backtest_pnl'] = row[1] if row[1] else 0.0

            return stats

    def close(self):
        pass # Handle automatically with context wrapper
