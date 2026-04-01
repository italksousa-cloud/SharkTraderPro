from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.preprocessing import StandardScaler
import pandas as pd
import numpy as np
import joblib
import json
import os
from logger_setup import logger
import config

class MLEngine:
    def __init__(self, model_path="shark_ml.model"):
        self.model_path = model_path
        self.model = None
        self.scaler = StandardScaler()
        self.metrics = {}
        self.target_features = [
            'confluence_score', 'rsi', 'macd', 'atr', 'bb_width', 'volume_change'
        ]
        self.load_model()

    def _prepare_features(self, df):
        if df.empty:
            return df
        
        # Helper to compute derived features
        df = df.copy()
        
        if 'bollinger_upper' in df.columns and 'bollinger_lower' in df.columns and 'close' in df.columns:
            df['bb_width'] = (df['bollinger_upper'] - df['bollinger_lower']) / df['close']
        elif 'bb_width' not in df.columns:
            df['bb_width'] = 0.0
            
        if 'volume' in df.columns and 'volume_prev' in df.columns:
            df['volume_change'] = df['volume'] / df['volume_prev']
        elif 'volume_change' not in df.columns:
            df['volume_change'] = 1.0
            
        # Ensure all target features exist
        for f in self.target_features:
            if f not in df.columns:
                df[f] = 0.0
                
        # Fill NaNs
        df.fillna(0, inplace=True)
        return df[self.target_features]

    def train(self, df, save_to_disk=True):
        if df is None or len(df) < 50:
            logger.warning("Insufficient data for ML training (>50 rows required).")
            return None, {}
            
        logger.info(f"Training ML Model on {len(df)} samples...")
        
        # Prepare target (1 for win, 0 for loss)
        if 'result' not in df.columns:
            logger.error("'result' column missing from training data.")
            return None, {}
            
        y = np.where(df['result'] == 'win', 1, 0)
        X = self._prepare_features(df)
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Scale
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Ensemble definitions
        rf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        gb = GradientBoostingClassifier(n_estimators=100, learning_rate=0.1, max_depth=3, random_state=42)
        
        self.model = VotingClassifier(estimators=[('rf', rf), ('gb', gb)], voting='soft')
        
        # Cross validation on training set
        cv_scores = cross_val_score(self.model, X_train_scaled, y_train, cv=5)
        logger.info(f"Cross-Validation Accuracy: {np.mean(cv_scores):.4f} (+/- {np.std(cv_scores) * 2:.4f})")
        
        # Fit and test
        self.model.fit(X_train_scaled, y_train)
        y_pred = self.model.predict(X_test_scaled)
        
        self.metrics = {
            'accuracy': float(accuracy_score(y_test, y_pred)),
            'precision_score': float(precision_score(y_test, y_pred, zero_division=0)),
            'recall': float(recall_score(y_test, y_pred, zero_division=0)),
            'f1_score': float(f1_score(y_test, y_pred, zero_division=0)),
            'training_samples': len(X),
            'validation_score': float(np.mean(cv_scores)),
            'features_used': self.target_features,
            'model_version': 'v1.1-ensemble'
        }
        
        # Feature Importance approximation (using Random Forest part)
        rf_fitted = self.model.named_estimators_['rf']
        importances = rf_fitted.feature_importances_
        feature_importance = {f: float(imp) for f, imp in zip(self.target_features, importances)}
        self.metrics['feature_importance'] = feature_importance
        
        logger.info(f"Training completed. Accuracy: {self.metrics['accuracy']:.4f}")
        
        if save_to_disk:
            self.save_model()
            
        return self.model, self.metrics

    def predict(self, features_dict):
        """
        Features dict should contain keys matching target_features natively or derivably.
        Returns confidence (0-1) of being a 'win'.
        """
        if self.model is None:
            # Fallback to random or neutral if no model trained
            return 0.50
            
        df = pd.DataFrame([features_dict])
        X = self._prepare_features(df)
        X_scaled = self.scaler.transform(X)
        
        # predict_proba returns [prob_loss, prob_win]
        proba = self.model.predict_proba(X_scaled)[0]
        confidence_win = proba[1]
        return float(confidence_win)

    def save_model(self):
        if self.model is not None:
            joblib.dump({'model': self.model, 'scaler': self.scaler, 'metrics': self.metrics}, self.model_path)
            logger.info(f"ML Model saved to {self.model_path}")

    def load_model(self):
        if os.path.exists(self.model_path):
            try:
                data = joblib.load(self.model_path)
                self.model = data['model']
                self.scaler = data['scaler']
                self.metrics = data['metrics']
                logger.info("ML Model loaded successfully.")
            except Exception as e:
                logger.error(f"Error loading ML model: {e}")
                self.model = None

    def get_current_metrics(self):
        return self.metrics

    def get_training_data_from_db(self, db):
        return db.get_ml_training_data(days=config.TRAING_DATA_DAYS)
