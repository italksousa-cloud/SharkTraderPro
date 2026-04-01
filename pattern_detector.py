import pandas as pd
import numpy as np
import talib
from logger_setup import logger

class PatternDetector:
    def __init__(self):
        # Mapeamento do TA-Lib para nosso formato
        self.patterns = {
            # PADRÕES DE REVERSÃO DE ALTA (8)
            'CDLHAMMER': {'name': 'Hammer', 'type': 'bullish', 'desc': 'Martelo, reversão de alta'},
            'CDLINVERTEDHAMMER': {'name': 'Inverted Hammer', 'type': 'bullish', 'desc': 'Martelo invertido, reversão de alta'},
            'CDLENGULFING_BULL': {'name': 'Bullish Engulfing', 'type': 'bullish', 'desc': 'Engolfo de alta'},
            'CDLPIERCING': {'name': 'Piercing Line', 'type': 'bullish', 'desc': 'Linha de perfuração, reversão de alta'},
            'CDLMORNINGSTAR': {'name': 'Morning Star', 'type': 'bullish', 'desc': 'Estrela da manhã, reversão de alta'},
            'CDL3WHITESOLDIERS': {'name': 'Three White Soldiers', 'type': 'bullish', 'desc': 'Três soldados brancos, reversão de alta'},
            'CDLDRAGONFLYDOJI': {'name': 'Dragonfly Doji', 'type': 'bullish', 'desc': 'Doji libélula, reversão de alta'},
            'CDLHARAMI_BULL': {'name': 'Bullish Harami', 'type': 'bullish', 'desc': 'Mulher grávida de alta'},

            # PADRÕES DE REVERSÃO DE BAIXA (8)
            'CDLHANGINGMAN': {'name': 'Hanging Man', 'type': 'bearish', 'desc': 'Homem enforcado, reversão de baixa'},
            'CDLSHOOTINGSTAR': {'name': 'Shooting Star', 'type': 'bearish', 'desc': 'Estrela cadente, reversão de baixa'},
            'CDLENGULFING_BEAR': {'name': 'Bearish Engulfing', 'type': 'bearish', 'desc': 'Engolfo de baixa'},
            'CDLDARKCLOUDCOVER': {'name': 'Dark Cloud Cover', 'type': 'bearish', 'desc': 'Nuvem negra, reversão de baixa'},
            'CDLEVENINGSTAR': {'name': 'Evening Star', 'type': 'bearish', 'desc': 'Estrela da tarde, reversão de baixa'},
            'CDL3BLACKCROWS': {'name': 'Three Black Crows', 'type': 'bearish', 'desc': 'Três corvos negros, reversão de baixa'},
            'CDLGRAVESTONEDOJI': {'name': 'Gravestone Doji', 'type': 'bearish', 'desc': 'Doji lápide, reversão de baixa'},
            'CDLHARAMI_BEAR': {'name': 'Bearish Harami', 'type': 'bearish', 'desc': 'Mulher grávida de baixa'},

            # PADRÕES DE CONTINUAÇÃO (5)
            'CDLRISEFALL3METHODS_BULL': {'name': 'Rising Three Methods', 'type': 'bullish', 'desc': 'Três métodos de alta, continuação'},
            'CDLRISEFALL3METHODS_BEAR': {'name': 'Falling Three Methods', 'type': 'bearish', 'desc': 'Três métodos de baixa, continuação'},
            'CDLMARUBOZU_BULL': {'name': 'Bullish Marubozu', 'type': 'bullish', 'desc': 'Marubozu de alta, continuação forte'},
            'CDLMARUBOZU_BEAR': {'name': 'Bearish Marubozu', 'type': 'bearish', 'desc': 'Marubozu de baixa, continuação forte'},
            'CDLSPINNINGTOP': {'name': 'Spinning Top', 'type': 'neutral', 'desc': 'Pião, indecisão/continuação'},

            # PADRÕES NEUTROS/DECISÃO (4)
            'CDLDOJI': {'name': 'Doji', 'type': 'neutral', 'desc': 'Doji clássico, indecisão'},
            'CDLLONGLEGGEDDOJI': {'name': 'Long Legged Doji', 'type': 'neutral', 'desc': 'Doji pernalta, grande indecisão'},
            # Tweezer Top/Bottom não tem funçao direta 100% no talib padrao, mas adaptaremos via engolfo/harami + tech ou lógica custom.
            # O TA-Lib padrão não exporta Tweezer. Substituíremos por duas lógicas customizadas:
            'CUSTOM_TWEEZER_TOP': {'name': 'Tweezer Top', 'type': 'bearish', 'desc': 'Topo em pinça, forte resistência'},
            'CUSTOM_TWEEZER_BOTTOM': {'name': 'Tweezer Bottom', 'type': 'bullish', 'desc': 'Fundo em pinça, forte suporte'}
        }

    def _detect_custom_patterns(self, df):
        """Detect patterns not natively supported perfectly by ta-lib like Tweezer."""
        res = {'CUSTOM_TWEEZER_TOP': np.zeros(len(df)), 'CUSTOM_TWEEZER_BOTTOM': np.zeros(len(df))}
        
        # Tweezer Top: Same Highs, first bullish, second bearish
        # Tweezer Bottom: Same Lows, first bearish, second bullish
        try:
            highs = df['high'].values
            lows = df['low'].values
            opens = df['open'].values
            closes = df['close'].values
            
            for i in range(1, len(df)):
                # Tolerance for "same" exact high/low (0.05%)
                tol_high = highs[i-1] * 0.0005
                tol_low = lows[i-1] * 0.0005
                
                # Top
                if abs(highs[i] - highs[i-1]) <= tol_high and closes[i-1] > opens[i-1] and closes[i] < opens[i]:
                    res['CUSTOM_TWEEZER_TOP'][i] = -100
                
                # Bottom
                if abs(lows[i] - lows[i-1]) <= tol_low and closes[i-1] < opens[i-1] and closes[i] > opens[i]:
                    res['CUSTOM_TWEEZER_BOTTOM'][i] = 100
                    
        except Exception as e:
            logger.error(f"Error in custom pattern detection: {e}")
            
        return res

    def detect_all_patterns(self, df):
        """
        Analisa os dados OHLCV e retorna os padrões encontrados no último candle fechado.
        df: DataFrame contendo ['open', 'high', 'low', 'close', 'volume']
        """
        if len(df) < 10:
            logger.warning("Not enough data to detect patterns (min 10 required)")
            return []

        open_p = df['open'].values
        high_p = df['high'].values
        low_p = df['low'].values
        close_p = df['close'].values

        detected = []
        
        # Último indice válido (o penúltimo se o último estiver "aberto", mas assumimos que df é sempre fechado ou we care about last row)
        last_idx = -1

        try:
            # 1. HAMMER
            res = talib.CDLHAMMER(open_p, high_p, low_p, close_p)
            if res[last_idx] > 0: detected.append(self._build_result('CDLHAMMER', 0.85))

            # 2. INVERTED HAMMER
            res = talib.CDLINVERTEDHAMMER(open_p, high_p, low_p, close_p)
            if res[last_idx] > 0: detected.append(self._build_result('CDLINVERTEDHAMMER', 0.80))

            # 3. ENGULFING (Retorna 100 pra Bullish e -100 pra Bearish)
            res = talib.CDLENGULFING(open_p, high_p, low_p, close_p)
            if res[last_idx] == 100: detected.append(self._build_result('CDLENGULFING_BULL', 0.90))
            if res[last_idx] == -100: detected.append(self._build_result('CDLENGULFING_BEAR', 0.90))

            # 4. PIERCING
            res = talib.CDLPIERCING(open_p, high_p, low_p, close_p)
            if res[last_idx] > 0: detected.append(self._build_result('CDLPIERCING', 0.85))

            # 5. MORNING STAR
            res = talib.CDLMORNINGSTAR(open_p, high_p, low_p, close_p)
            if res[last_idx] > 0: detected.append(self._build_result('CDLMORNINGSTAR', 0.95))

            # 6. THREE WHITE SOLDIERS
            res = talib.CDL3WHITESOLDIERS(open_p, high_p, low_p, close_p)
            if res[last_idx] > 0: detected.append(self._build_result('CDL3WHITESOLDIERS', 0.95))

            # 7. DRAGONFLY DOJI
            res = talib.CDLDRAGONFLYDOJI(open_p, high_p, low_p, close_p)
            if res[last_idx] > 0: detected.append(self._build_result('CDLDRAGONFLYDOJI', 0.80))

            # 8. HARAMI (Retorna 100 pra Bullish e -100 pra Bearish)
            res = talib.CDLHARAMI(open_p, high_p, low_p, close_p)
            if res[last_idx] == 100: detected.append(self._build_result('CDLHARAMI_BULL', 0.75))
            if res[last_idx] == -100: detected.append(self._build_result('CDLHARAMI_BEAR', 0.75))

            # 9. HANGING MAN
            res = talib.CDLHANGINGMAN(open_p, high_p, low_p, close_p)
            if res[last_idx] < 0: detected.append(self._build_result('CDLHANGINGMAN', 0.85))

            # 10. SHOOTING STAR
            res = talib.CDLSHOOTINGSTAR(open_p, high_p, low_p, close_p)
            if res[last_idx] < 0: detected.append(self._build_result('CDLSHOOTINGSTAR', 0.85))

            # 11. DARK CLOUD COVER
            res = talib.CDLDARKCLOUDCOVER(open_p, high_p, low_p, close_p)
            if res[last_idx] < 0: detected.append(self._build_result('CDLDARKCLOUDCOVER', 0.85))

            # 12. EVENING STAR
            res = talib.CDLEVENINGSTAR(open_p, high_p, low_p, close_p)
            if res[last_idx] < 0: detected.append(self._build_result('CDLEVENINGSTAR', 0.95))

            # 13. THREE BLACK CROWS
            res = talib.CDL3BLACKCROWS(open_p, high_p, low_p, close_p)
            if res[last_idx] < 0: detected.append(self._build_result('CDL3BLACKCROWS', 0.95))

            # 14. GRAVESTONE DOJI
            res = talib.CDLGRAVESTONEDOJI(open_p, high_p, low_p, close_p)
            if res[last_idx] < 0: detected.append(self._build_result('CDLGRAVESTONEDOJI', 0.80))

            # 15. RISING THREE METHODS (100) / FALLING THREE METHODS (-100)
            res = talib.CDLRISEFALL3METHODS(open_p, high_p, low_p, close_p)
            if res[last_idx] == 100: detected.append(self._build_result('CDLRISEFALL3METHODS_BULL', 0.90))
            if res[last_idx] == -100: detected.append(self._build_result('CDLRISEFALL3METHODS_BEAR', 0.90))

            # 16. MARUBOZU
            res = talib.CDLMARUBOZU(open_p, high_p, low_p, close_p)
            if res[last_idx] == 100: detected.append(self._build_result('CDLMARUBOZU_BULL', 0.90))
            if res[last_idx] == -100: detected.append(self._build_result('CDLMARUBOZU_BEAR', 0.90))

            # 17. SPINNING TOP
            res = talib.CDLSPINNINGTOP(open_p, high_p, low_p, close_p)
            if res[last_idx] != 0: detected.append(self._build_result('CDLSPINNINGTOP', 0.50)) # Neutral

            # 18. DOJI
            res = talib.CDLDOJI(open_p, high_p, low_p, close_p)
            if res[last_idx] != 0: detected.append(self._build_result('CDLDOJI', 0.60))
            
            # 19. LONG LEGGED DOJI
            res = talib.CDLLONGLEGGEDDOJI(open_p, high_p, low_p, close_p)
            if res[last_idx] != 0: detected.append(self._build_result('CDLLONGLEGGEDDOJI', 0.65))

            # 20. CUSTOM TWEEZER
            custom_res = self._detect_custom_patterns(df)
            if custom_res['CUSTOM_TWEEZER_TOP'][last_idx] < 0:
                detected.append(self._build_result('CUSTOM_TWEEZER_TOP', 0.85))
            if custom_res['CUSTOM_TWEEZER_BOTTOM'][last_idx] > 0:
                detected.append(self._build_result('CUSTOM_TWEEZER_BOTTOM', 0.85))

        except Exception as e:
            logger.error(f"Error detecting talib patterns: {e}")

        return detected

    def _build_result(self, code, confidence):
        data = self.patterns.get(code)
        if not data:
            return None
        return {
            'name': data['name'],
            'type': data['type'],
            'confidence': confidence,
            'description': data['desc']
        }
