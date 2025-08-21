"""
Configuration management for Vercel serverless deployment
"""

import json
import os
from typing import Dict, List, Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables for Vercel"""
    
    model_config = SettingsConfigDict(
        case_sensitive=False
    )
    
    # TradingView webhook security
    tv_shared_secret: str = Field(default="", description="TradingView webhook shared secret")
    
    # Telegram configuration
    telegram_bot_token: str = Field(default="", description="Telegram bot token")
    telegram_chat_id_default: str = Field(default="", description="Default Telegram chat ID")
    telegram_admin_ids: str = Field(default="", description="Comma-separated admin user IDs")
    
    # Optional chat routing
    telegram_tf_chat_map: str = Field(default="{}", description="JSON mapping timeframes to chat IDs")
    telegram_symbol_chat_map: str = Field(default="{}", description="JSON mapping symbols to chat IDs") 
    
    # Trading configuration
    default_pairs: str = Field(default="BTCUSDT,ETHUSDT,ETHBTC,ADAUSDT", description="Default coin pairs")
    supported_timeframes: str = Field(default="5,15,60,240,D", description="Supported timeframes")
    
    # Display configuration
    tz_display: str = Field(default="Europe/London", description="Display timezone")
    
    # Vercel KV configuration
    kv_rest_api_url: Optional[str] = Field(default=None, description="Vercel KV REST API URL")
    kv_rest_api_token: Optional[str] = Field(default=None, description="Vercel KV REST API Token")
    
    # Performance configuration
    idempotency_ttl_days: int = Field(default=7, description="Signal cache TTL in days")
    
    # Telegram retry configuration
    telegram_max_retries: int = Field(default=3, description="Max Telegram send retries")
    telegram_retry_delays: str = Field(default="1,2,4", description="Retry delays in seconds")
    
    @validator("telegram_tf_chat_map")
    def validate_tf_chat_map(cls, v: str) -> Dict[str, str]:
        """Parse and validate timeframe chat mapping"""
        if not v or v == "{}":
            return {}
        try:
            parsed = json.loads(v)
            if not isinstance(parsed, dict):
                raise ValueError("Must be a JSON object")
            return {str(k): str(v) for k, v in parsed.items()}
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
    
    @validator("telegram_symbol_chat_map")  
    def validate_symbol_chat_map(cls, v: str) -> Dict[str, str]:
        """Parse and validate symbol chat mapping"""
        if not v or v == "{}":
            return {}
        try:
            parsed = json.loads(v)
            if not isinstance(parsed, dict):
                raise ValueError("Must be a JSON object")
            return {str(k).upper(): str(v) for k, v in parsed.items()}
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
    
    @validator("telegram_admin_ids")
    def validate_admin_ids(cls, v: str) -> List[int]:
        """Parse and validate admin user IDs"""
        if not v:
            return []
        try:
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        except ValueError as e:
            raise ValueError(f"Admin IDs must be integers: {e}")
    
    @validator("default_pairs")
    def validate_default_pairs(cls, v: str) -> List[str]:
        """Parse and validate default trading pairs"""
        if not v:
            return []
        pairs = [x.strip().upper() for x in v.split(",") if x.strip()]
        # Basic validation - should contain known quote currencies
        valid_quotes = ["USDT", "BTC", "ETH", "BUSD"]
        for pair in pairs:
            if not any(pair.endswith(quote) for quote in valid_quotes):
                raise ValueError(f"Invalid pair format: {pair}")
        return pairs
    
    @validator("supported_timeframes")
    def validate_supported_timeframes(cls, v: str) -> List[str]:
        """Parse and validate supported timeframes"""
        if not v:
            return []
        timeframes = [x.strip() for x in v.split(",") if x.strip()]
        # Validate against known TradingView timeframes
        valid_tfs = ["1", "3", "5", "15", "30", "45", "60", "120", "180", "240", "360", "720", "D", "W", "M"]
        for tf in timeframes:
            if tf not in valid_tfs:
                raise ValueError(f"Invalid timeframe: {tf}")
        return timeframes
    
    @validator("telegram_retry_delays")
    def validate_retry_delays(cls, v: str) -> List[float]:
        """Parse and validate retry delays"""
        if not v:
            return [1.0, 2.0, 4.0]
        try:
            return [float(x.strip()) for x in v.split(",") if x.strip()]
        except ValueError as e:
            raise ValueError(f"Retry delays must be numbers: {e}")
    
    @property
    def admin_ids_list(self) -> List[int]:
        """Get admin IDs as list"""
        return self.telegram_admin_ids
    
    @property
    def pairs_list(self) -> List[str]:
        """Get default pairs as list"""
        return self.default_pairs
    
    @property
    def timeframes_list(self) -> List[str]:
        """Get supported timeframes as list"""
        return self.supported_timeframes
    
    @property
    def retry_delays_list(self) -> List[float]:
        """Get retry delays as list"""
        return self.telegram_retry_delays
    
    @property
    def tf_chat_map(self) -> Dict[str, str]:
        """Get timeframe chat mapping"""
        return self.telegram_tf_chat_map
    
    @property
    def symbol_chat_map(self) -> Dict[str, str]:
        """Get symbol chat mapping"""
        return self.telegram_symbol_chat_map
    
    @property
    def has_kv_config(self) -> bool:
        """Check if Vercel KV is configured"""
        return bool(self.kv_rest_api_url and self.kv_rest_api_token)
    
    def get_chat_id_for_signal(self, symbol: str, timeframe: str) -> str:
        """Get appropriate chat ID for a signal based on routing rules"""
        symbol = symbol.upper()
        
        # Priority 1: Symbol-specific mapping
        if symbol in self.symbol_chat_map:
            return self.symbol_chat_map[symbol]
        
        # Priority 2: Timeframe-specific mapping
        if timeframe in self.tf_chat_map:
            return self.tf_chat_map[timeframe]
        
        # Priority 3: Default chat
        return self.telegram_chat_id_default
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user ID is in admin list"""
        return user_id in self.admin_ids_list
    
    def is_symbol_allowed(self, symbol: str) -> bool:
        """Check if symbol is in allowed list (will be dynamic with database)"""
        return symbol.upper() in self.pairs_list
    
    def is_timeframe_supported(self, timeframe: str) -> bool:
        """Check if timeframe is supported"""
        return timeframe in self.timeframes_list
    
    def normalize_timeframe(self, timeframe: str) -> Optional[str]:
        """Normalize TradingView timeframe to display format"""
        tf_map = {
            "5": "5m",
            "15": "15m", 
            "60": "1h",
            "240": "4h",
            "D": "1D"
        }
        return tf_map.get(timeframe)
    
    def get_chart_interval(self, timeframe: str) -> str:
        """Get TradingView chart interval for URL"""
        chart_map = {
            "5": "5",
            "15": "15",
            "60": "60", 
            "240": "240",
            "D": "1D"
        }
        return chart_map.get(timeframe, timeframe)


# Global settings instance
settings = Settings()