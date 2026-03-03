"""
Real-time market data collection with caching and streaming capabilities.
Handles multiple exchanges and ensures data consistency.
"""
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass
import asyncio
from collections import defaultdict

from config import config
from firebase_admin import firestore

logger = logging.getLogger(__name__)

@dataclass
class MarketData:
    """Structured market data container"""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    timeframe: str
    
class DataCollector:
    """Collects and manages market data from multiple sources"""
    
    def __init__(self, exchange_id: str = 'binance'):
        self.logger = logging.getLogger(f"{__name__}.{exchange_id}")
        self.exchange_id = exchange_id
        self.db = config.get_firebase_client()
        self._initialize_exchange()
        self.data_cache = defaultdict(dict)
        
    def _initialize_exchange(self) -> None:
        """Initialize exchange connection with error handling"""
        try:
            exchange_config = config.get_exchange_config()
            exchange_class = getattr(ccxt, self.exchange_id)
            self.exchange = exchange_class({
                'apiKey': exchange_config['api_key'],
                'secret': exchange_config['secret'],
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'}
            })
            
            if exchange_config['sandbox']:
                self.exchange.set_sandbox_mode(True)
                
            self.logger.info(f"Connected to {self.exchange_id} exchange")
        except AttributeError:
            self.logger.error(f"Exchange {self.exchange_id} not found in ccxt")
            raise
        except Exception as e:
            self.logger.error(f"Exchange initialization failed: {str(e)}")
            raise
    
    def get_historical_data(self, symbol: str, timeframe: str, 
                           limit: int = 1000) -> pd.DataFrame:
        """
        Fetch historical OHLCV data with caching
        """
        cache_key = f"{symbol}_{timeframe}"
        
        # Check cache first
        if cache_key in self.data_cache:
            cached_data = self.data_cache[cache_key]
            if len(cached_data) >= limit:
                self.logger.debug(f"Returning cached data for {cache_key}")
                return cached_data.tail(limit)
        
        try:
            self.logger.info(f"Fetching {limit} candles for {symbol} ({timeframe})")
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Cache the data
            self.data_cache[cache_key] = df
            
            # Store in Firestore for persistence
            self._store_to_firestore(symbol, timeframe, df)
            
            return df
            
        except ccxt.NetworkError as e:
            self.logger.error(f"Network error fetching data: {str(e)}")
            # Try to return cached data if available
            if cache_key in self.data_cache:
                self.logger.warning("Returning stale cached data due to network error")
                return self.data_cache[cache_key].tail(limit)
            raise
        except Exception as e:
            self.logger.error(f"Error fetching historical data: {str(e)}")
            raise
    
    def _store_to_firestore(self, symbol: str, timeframe: str, df: pd.DataFrame) -> None:
        """Store