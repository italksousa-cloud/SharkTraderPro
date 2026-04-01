import os

# --- PARES DE TRADING ---
MAX_SYMBOLS = 500

# --- TIMEFRAMES ---
# SOMENTE estes permitidos
TIMEFRAMES = ["15m", "1h", "4h", "1d"]

# --- GERENCIAMENTO DE RISCO ---
RISK_PER_TRADE_PCT = 2.0  # Max 2% loss per trade
TAKE_PROFIT_RATIO_1 = 2.0 # 1:2 risk/reward
TAKE_PROFIT_RATIO_2 = 3.0 # 1:3 risk/reward
MAX_DRAWDOWN_PCT = 10.0   # 10% max drawdown
MAX_SIMULTANEOUS_TRADES = 3
MAX_DAILY_LOSS_PCT = 5.0

# --- MACHINE LEARNING ---
ML_CONFIDENCE_THRESHOLD = 0.70
RETRAIN_EVERY = 50  # Retreinar a cada 50 trades
TRAING_DATA_DAYS = 90 # Dias retroativos para buscar dados de treino

# --- PADRÕES GRÁFICOS PARÂMETROS ---
MIN_BODY_SIZE_PCT = 0.1 # % min of body size vs full candle
DOJI_MAX_BODY_PCT = 5.0 # Max body size in % to be considered doji
ENGULFING_MIN_SIZE_FACTOR = 1.1 # Engulfing candle must be at least 1.1x larger

# --- DATABASE ---
DB_PATH = "shark_trader.db"

# --- INDICATORS ---
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BB_PERIOD = 20
BB_STD = 2.0
ATR_PERIOD = 14

# --- API e EXCHANGES ---
BYBIT_TESTNET = False # Set to True for testnet
RATE_LIMIT_RETRIES = 3
RATE_LIMIT_DELAY = 1.0 # Base delay in seconds

# --- TELEGRAM ---
TELEGRAM_ENABLED = os.getenv("TELEGRAM_TOKEN") is not None and os.getenv("TELEGRAM_CHAT_ID") is not None
