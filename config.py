"""
Configuration and environment management for the trading framework.
Centralizes all config to prevent scattered environment variables.
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional
import firebase_admin
from firebase_admin import credentials, firestore
import logging

class TradingConfig:
    """Central configuration manager for the trading system"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._validate_environment()
        
    def _validate_environment(self) -> None:
        """Validate all required environment variables exist"""
        required_vars = [
            'FIREBASE_CREDENTIALS_PATH',
            'TELEGRAM_BOT_TOKEN',
            'TELEGRAM_CHAT_ID',
            'EXCHANGE_API_KEY',
            'EXCHANGE_SECRET'
        ]
        
        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            error_msg = f"Missing environment variables: {missing}"
            self.logger.critical(error_msg)
            raise EnvironmentError(error_msg)
    
    def get_firebase_client(self) -> firestore.Client:
        """Initialize and return Firebase Firestore client"""
        try:
            cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
            if not Path(cred_path).exists():
                raise FileNotFoundError(f"Firebase credentials not found at: {cred_path}")
            
            cred = credentials.Certificate(cred_path)
            app = firebase_admin.initialize_app(cred)
            return firestore.client(app=app)
        except Exception as e:
            self.logger.error(f"Firebase initialization failed: {str(e)}")
            raise
    
    def get_exchange_config(self) -> Dict[str, str]:
        """Get exchange API configuration"""
        return {
            'api_key': os.getenv('EXCHANGE_API_KEY'),
            'secret': os.getenv('EXCHANGE_SECRET'),
            'sandbox': os.getenv('EXCHANGE_SANDBOX', 'true').lower() == 'true'
        }
    
    @property
    def telegram_config(self) -> Dict[str, str]:
        """Get Telegram notification configuration"""
        return {
            'bot_token': os.getenv('TELEGRAM_BOT_TOKEN'),
            'chat_id': os.getenv('TELEGRAM_CHAT_ID')
        }
    
    @property
    def trading_params(self) -> Dict[str, Any]:
        """Get trading-specific parameters"""
        return {
            'max_position_size': float(os.getenv('MAX_POSITION_SIZE', '1000.0')),
            'max_open_positions': int(os.getenv('MAX_OPEN_POSITIONS', '5')),
            'risk_per_trade': float(os.getenv('RISK_PER_TRADE', '0.02')),
            'default_timeframe': os.getenv('DEFAULT_TIMEFRAME', '1h')
        }

# Global configuration instance
config = TradingConfig()