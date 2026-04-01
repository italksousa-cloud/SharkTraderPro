from exchange_manager import ExchangeManager
from pattern_detector import PatternDetector
from logger_setup import logger
import config

class MultiTimeframeAnalyzer:
    def __init__(self, exchange_manager: ExchangeManager, pattern_detector: PatternDetector):
        self.exchange = exchange_manager
        self.detector = pattern_detector
        # Pesos para o cálculo de confluence (1d > 4h > 1h > 15m)
        self.weights = {
            '1d': 0.40,
            '4h': 0.30,
            '1h': 0.20,
            '15m': 0.10
        }

    def analyze(self, symbol):
        """
        Analyses the symbol across all configured timeframes.
        Returns a dictionary with confluence score and details per timeframe.
        """
        logger.info(f"Starting Multi-Timeframe Analysis for {symbol}...")
        
        results_by_tf = {}
        tf_sentiment = {}
        
        for tf in config.TIMEFRAMES:
            try:
                df = self.exchange.get_ohlcv(symbol, tf, limit=50)
                if df is None or len(df) == 0:
                    logger.warning(f"Failed to fetch data for {symbol} on {tf}")
                    results_by_tf[tf] = []
                    tf_sentiment[tf] = 0
                    continue

                patterns = self.detector.detect_all_patterns(df)
                results_by_tf[tf] = patterns
                
                # Assign sentiment score to this timeframe
                # Sum of bullish confidences - Sum of bearish confidences
                score = 0
                for p in patterns:
                    if p['type'] == 'bullish':
                        score += p['confidence']
                    elif p['type'] == 'bearish':
                        score -= p['confidence']
                
                # Cap score between -1 and 1
                if score > 1: score = 1
                if score < -1: score = -1
                
                tf_sentiment[tf] = score
                logger.debug(f"{symbol} @ {tf} -> Sentiment: {score:.2f}, Patterns: {[p['name'] for p in patterns]}")
                
            except Exception as e:
                logger.error(f"Error analyzing {symbol} on {tf}: {e}")
                results_by_tf[tf] = []
                tf_sentiment[tf] = 0

        # Calculate weighted confluence score (0 to 100 for strength, with directional sign)
        # Result meaning: +X% (Bullish Confluence), -X% (Bearish Confluence)
        raw_confluence = 0.0
        total_weight = 0.0
        
        for tf, weight in self.weights.items():
            if tf in tf_sentiment:
                raw_confluence += tf_sentiment[tf] * weight
                total_weight += weight
                
        if total_weight > 0:
            final_confluence = (raw_confluence / total_weight) * 100
        else:
            final_confluence = 0.0

        direction = "neutral"
        if final_confluence > 15:
            direction = "bullish"
        elif final_confluence < -15:
            direction = "bearish"

        return {
            "symbol": symbol,
            "direction": direction, # bullish/bearish/neutral
            "confluence_score": abs(final_confluence), # 0-100 magnitude
            "raw_confluence": final_confluence, # -100 to 100
            "timeframes": results_by_tf,
            "weights_used": self.weights
        }
