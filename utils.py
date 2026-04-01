import talib
import requests
import json
from logger_setup import logger
import config
import os

def format_currency(value):
    return f"${value:,.2f}"

def format_pct(value):
    return f"{value:+.2f}%"
    
def calculate_indicators(df):
    """Calculates common indicators safely."""
    if df is None or len(df) < 50:
        return df
        
    df = df.copy()
    close_p = df['close'].values
    high_p = df['high'].values
    low_p = df['low'].values
    
    # RSI
    df['rsi'] = talib.RSI(close_p, timeperiod=config.RSI_PERIOD)
    
    # MACD
    macd, macdsignal, macdhist = talib.MACD(close_p, fastperiod=config.MACD_FAST, slowperiod=config.MACD_SLOW, signalperiod=config.MACD_SIGNAL)
    df['macd'] = macd
    df['macd_signal'] = macdsignal
    df['macd_hist'] = macdhist
    
    # Bollinger Bands
    upper, middle, lower = talib.BBANDS(close_p, timeperiod=config.BB_PERIOD, nbdevup=config.BB_STD, nbdevdn=config.BB_STD, matype=0)
    df['bollinger_upper'] = upper
    df['bollinger_lower'] = lower
    df['bollinger_mid'] = middle
    
    # ATR
    df['atr'] = talib.ATR(high_p, low_p, close_p, timeperiod=config.ATR_PERIOD)
    
    return df

def get_trend_direction(df):
    """Simple trend detection based on SMA50 vs SMA200"""
    if len(df) < 200:
        return "neutral"
    
    close_p = df['close'].values
    sma50 = talib.SMA(close_p, timeperiod=50)[-1]
    sma200 = talib.SMA(close_p, timeperiod=200)[-1]
    
    if np.isnan(sma50) or np.isnan(sma200):
        return "neutral"
        
    if sma50 > sma200:
        return "uptrend"
    elif sma50 < sma200:
        return "downtrend"
    return "neutral"

def send_telegram_message(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        return
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logger.error(f"Telegram notification failed: {e}")
