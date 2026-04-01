import ccxt
import time
import os
from dotenv import load_dotenv
import pandas as pd
from logger_setup import logger
import config

load_dotenv()

class ExchangeManager:
    def __init__(self, testnet=config.BYBIT_TESTNET):
        self.api_key = os.getenv("BYBIT_API_KEY")
        self.secret_key = os.getenv("BYBIT_SECRET_KEY")
        
        exchange_class = ccxt.bybit
        self.exchange = exchange_class({
            'apiKey': self.api_key,
            'secret': self.secret_key,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future', # Defaulting to futures
            }
        })
        
        if testnet:
            self.exchange.set_sandbox_mode(True)
            logger.info("Exchange initialized in TESTNET mode.")
        else:
            logger.info("Exchange initialized in REAL/PRODUCTION mode.")

    def _retry_call(self, func, *args, **kwargs):
        """Wrapper for handling rate limits and connection errors."""
        retries = config.RATE_LIMIT_RETRIES
        delay = config.RATE_LIMIT_DELAY
        for i in range(retries):
            try:
                return func(*args, **kwargs)
            except ccxt.RateLimitExceeded as e:
                logger.warning(f"Rate limit exceeded. Retrying in {delay}s ({i+1}/{retries}). Error: {e}")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            except ccxt.NetworkError as e:
                logger.error(f"Network error. Retrying in {delay}s ({i+1}/{retries}). Error: {e}")
                time.sleep(delay)
            except Exception as e:
                logger.error(f"Unexpected error during API call: {e}")
                raise e
        logger.error("Max retries exceeded.")
        return None

    def get_top_futures(self, limit=500):
        def fetch():
            # Get linear markets
            if not self.exchange.markets:
                self.exchange.load_markets()
            
            tickers = self.exchange.fetch_tickers(params={'category': 'linear'})
            
            valid_tickers = []
            for symbol, ticker in tickers.items():
                if symbol in self.exchange.markets:
                    market = self.exchange.markets[symbol]
                    if market['linear'] and market['quote'] == 'USDT' and market['active']:
                        valid_tickers.append(ticker)
            
            # Sort by quote volume descending
            valid_tickers.sort(key=lambda x: x.get('quoteVolume') or 0, reverse=True)
            
            return [t['symbol'] for t in valid_tickers[:limit]]
            
        return self._retry_call(fetch)

    def get_ohlcv(self, symbol, timeframe, limit=500):
        if timeframe not in config.TIMEFRAMES:
            logger.error(f"Invalid timeframe: {timeframe}. Allowed: {config.TIMEFRAMES}")
            return None
            
        def fetch():
            return self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
        data = self._retry_call(fetch)
        if data:
            df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        return None

    def get_order_book(self, symbol, limit=20):
        def fetch():
            return self.exchange.fetch_order_book(symbol, limit=limit)
        return self._retry_call(fetch)

    def get_ticker(self, symbol):
        def fetch():
            return self.exchange.fetch_ticker(symbol)
        return self._retry_call(fetch)

    def get_balance(self, currency="USDT"):
        def fetch():
            return self.exchange.fetch_balance()
        balance = self._retry_call(fetch)
        if balance and currency in balance:
            return {
                "free": balance[currency]['free'],
                "used": balance[currency]['used'],
                "total": balance[currency]['total']
            }
        return {"free": 0, "used": 0, "total": 0}

    def place_order(self, symbol, type, side, amount, price=None, params=None):
        if params is None:
            params = {}
        def fetch():
            return self.exchange.create_order(symbol, type, side, amount, price, params)
        logger.info(f"Placing {side} order for {amount} {symbol} @ {price if price else 'MARKET'}")
        return self._retry_call(fetch)
