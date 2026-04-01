from database import DatabaseManager
from logger_setup import logger
import config
from datetime import datetime

class MLRetrainer:
    def __init__(self, db: DatabaseManager, ml_engine, config_module):
        self.db = db
        self.ml_engine = ml_engine
        self.config = config_module
        self.threshold = self.config.ML_CONFIDENCE_THRESHOLD
        self.disabled_patterns = []
        self.pattern_weights = {}

    def auto_retrain(self):
        logger.info("Checking for ML auto-retrain...")
        trades_since_last = self.db.get_total_trades_since_last_training()
        
        if trades_since_last >= self.config.RETRAIN_EVERY:
            logger.info(f"Auto-retrain triggered ({trades_since_last} new trades).")
            
            # Puxa dados do banco
            df = self.db.get_ml_training_data(days=self.config.TRAING_DATA_DAYS)
            
            if len(df) < 100:
                logger.warning("Not enough data to retrain yet. Needs at least 100 samples.")
                return False
                
            # Treina novo modelo
            new_model, new_metrics = self.ml_engine.train(df, save_to_disk=False)
            
            # Compara métricas (accuracy ou f1_score)
            current_metrics = self.ml_engine.get_current_metrics()
            
            if new_metrics['accuracy'] >= current_metrics.get('accuracy', 0):
                logger.info(f"New model is better ({new_metrics['accuracy']:.4f} > {current_metrics.get('accuracy', 0):.4f}). Saving...")
                self.ml_engine.model = new_model
                self.ml_engine.metrics = new_metrics
                self.ml_engine.save_model()
                self.db.save_ml_training(new_metrics)
                logger.info("Auto-retrain completed and saved.")
                return True
            else:
                logger.info(f"New model is worse ({new_metrics['accuracy']:.4f} < {current_metrics.get('accuracy', 0):.4f}). Discarding.")
                return False
        else:
            logger.info(f"Not enough trades since last training ({trades_since_last}/{self.config.RETRAIN_EVERY}).")
            return False

    def evaluate_patterns(self):
        logger.info("Evaluating pattern performances...")
        df = self.db.get_pattern_win_rates()
        if df.empty:
            logger.warning("No pattern performance data available.")
            return {}

        self.disabled_patterns = []
        self.pattern_weights = {}
        
        for index, row in df.iterrows():
            name = row['pattern_name']
            wr = row['win_rate']
            times = row['times_detected']
            
            if times >= 20 and wr < 40.0:
                self.disabled_patterns.append(name)
                logger.info(f"Pattern {name} disabled (Win Rate: {wr:.2f}%, {times} trades)")
            elif wr > 70.0:
                self.pattern_weights[name] = 1.5 # Boost
                logger.info(f"Pattern {name} weight boosted (Win Rate: {wr:.2f}%)")
            else:
                self.pattern_weights[name] = 1.0 # Normal

        return {
            "disabled": self.disabled_patterns,
            "weights": self.pattern_weights
        }

    def adjust_confidence_threshold(self):
        logger.info("Adjusting confidence threshold...")
        # Lógica simplificada: se win rate recente tá baixo, sobe o threshold
        df = self.db.get_trades(is_backtest=False)
        if len(df) < 50:
            return
            
        # Pega ultimos 50 reais
        last_50 = df.head(50)
        wins = len(last_50[last_50['result'] == 'win'])
        wr = wins / 50.0
        
        old_threshold = self.threshold
        if wr < 0.45:
            # Perdas! Apertar confiabilidade
            self.threshold = min(0.90, self.threshold + 0.05)
        elif wr > 0.65:
            # Ganhando bastante! Podemos relaxar um pouco para pegar mais trades
            self.threshold = max(0.50, self.threshold - 0.05)
            
        if abs(self.threshold - old_threshold) >= 0.05:
            logger.info(f"Confidence threshold updated from {old_threshold:.2f} to {self.threshold:.2f}")

    def generate_report(self):
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT accuracy FROM ml_training_log ORDER BY timestamp ASC")
            evolution = [r[0] for r in cursor.fetchall()]
        
        df = self.db.get_pattern_win_rates()
        top_5 = df.head(5).to_dict(orient='records') if not df.empty else []
        worst_5 = df.tail(5).to_dict(orient='records') if not df.empty else []

        return {
            "accuracy_evolution": evolution,
            "top_5_patterns": top_5,
            "worst_5_patterns": worst_5,
            "disabled_patterns": self.disabled_patterns,
            "current_threshold": self.threshold
        }

    def get_learning_summary(self):
        report = self.generate_report()
        text = "🤖 ML LEARNING SUMMARY\n"
        acc_evo = report['accuracy_evolution']
        if acc_evo:
            text += f"- Initial Accuracy: {acc_evo[0]:.2f}\n"
            text += f"- Current Accuracy: {acc_evo[-1]:.2f}\n"
            
        text += f"- Current Confidence Threshold: {report['current_threshold']:.2f}\n"
        text += f"- Disabled Patterns: {', '.join(report['disabled_patterns']) if report['disabled_patterns'] else 'None'}\n"
        
        text += "- Top 3 Patterns:\n"
        for p in report['top_5_patterns'][:3]:
            text += f"   * {p['pattern_name']} ({p['win_rate']:.1f}% WR)\n"
            
        return text
