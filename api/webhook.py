"""
Vercel serverless function for TradingView webhook
"""

import json
import secrets
from datetime import datetime
from typing import Any, Dict

from pydantic import BaseModel, Field, validator

from lib.config import settings
from lib.database import save_signal, get_enabled_pairs
from lib.telegram_bot import send_signal_message

class TradingViewPayload(BaseModel):
    """TradingView webhook payload validation"""
    
    event: str = Field(..., description="Signal event type")
    symbol: str = Field(..., description="Trading symbol")
    timeframe: str = Field(..., description="Chart timeframe")
    bar_time: int = Field(..., description="Bar timestamp in milliseconds")
    entry: float = Field(..., gt=0, description="Entry price")
    stop: float = Field(..., gt=0, description="Stop loss price")
    target: float = Field(..., gt=0, description="Take profit price")
    rr: float = Field(..., gt=0, description="Risk/reward ratio")
    signal_id: str = Field(..., description="Unique signal identifier")
    
    @validator("symbol")
    def validate_symbol(cls, v: str) -> str:
        """Validate and normalize symbol"""
        return v.upper().strip()
    
    @validator("timeframe")
    def validate_timeframe(cls, v: str) -> str:
        """Validate timeframe against supported values"""
        if v not in settings.timeframes_list:
            raise ValueError(f"Unsupported timeframe: {v}. Supported: {settings.timeframes_list}")
        return v
    
    @validator("event")
    def validate_event(cls, v: str) -> str:
        """Validate event type"""
        allowed_events = ["EMA_BOUNCE_BUY"]
        if v not in allowed_events:
            raise ValueError(f"Invalid event: {v}. Allowed: {allowed_events}")
        return v
    
    @validator("stop")
    def validate_stop_vs_entry(cls, v: float, values: Dict[str, Any]) -> float:
        """Validate stop loss is below entry for long positions"""
        if "entry" in values and v >= values["entry"]:
            raise ValueError("Stop loss must be below entry price for long positions")
        return v
    
    @validator("target")
    def validate_target_vs_entry(cls, v: float, values: Dict[str, Any]) -> float:
        """Validate target is above entry for long positions"""
        if "entry" in values and v <= values["entry"]:
            raise ValueError("Target must be above entry price for long positions")
        return v

def default(request):
    """Vercel serverless handler for TradingView webhook"""
    
    # Handle preflight OPTIONS request
    if request.method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, X-TV-Secret"
            }
        }
    
    # Only allow POST requests
    if request.method != "POST":
        return {
            "statusCode": 405,
            "body": json.dumps({"error": "Method not allowed"})
        }
    
    try:
        # Verify shared secret
        tv_secret = request.headers.get("x-tv-secret") or request.headers.get("X-TV-Secret")
        
        if not tv_secret:
            return {
                "statusCode": 401,
                "body": json.dumps({"error": "Missing X-TV-Secret header"})
            }
        
        # Use constant-time comparison to prevent timing attacks
        if not secrets.compare_digest(tv_secret, settings.tv_shared_secret):
            return {
                "statusCode": 401,
                "body": json.dumps({"error": "Invalid shared secret"})
            }
        
        # Parse request body
        try:
            if hasattr(request, 'json') and request.json:
                body_data = request.json
            else:
                body_data = json.loads(request.body)
        except (json.JSONDecodeError, AttributeError):
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid JSON payload"})
            }
        
        # Validate payload
        try:
            payload = TradingViewPayload(**body_data)
        except Exception as e:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Validation error: {str(e)}"})
            }
        
        # Process webhook asynchronously
        import asyncio
        
        # For Vercel, we need to handle async properly
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(process_webhook(payload))
            return result
        finally:
            loop.close()
            
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Internal server error",
                "timestamp": datetime.utcnow().isoformat()
            })
        }

async def process_webhook(payload: TradingViewPayload) -> dict:
    """Process the validated webhook payload"""
    
    try:
        # Verify symbol is allowed
        enabled_pairs = await get_enabled_pairs()
        if payload.symbol not in enabled_pairs:
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": f"Symbol {payload.symbol} is not in enabled pairs list"
                })
            }
        
        # Save signal to database (with idempotency check)
        signal_saved = await save_signal(
            signal_id=payload.signal_id,
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            event=payload.event,
            bar_time=payload.bar_time,
            entry=payload.entry,
            stop=payload.stop,
            target=payload.target,
            rr=payload.rr
        )
        
        if signal_saved:
            # Send to Telegram asynchronously (fire and forget)
            asyncio.create_task(send_signal_message(
                signal_id=payload.signal_id,
                symbol=payload.symbol,
                timeframe=payload.timeframe,
                event=payload.event,
                bar_time=payload.bar_time,
                entry=payload.entry,
                stop=payload.stop,
                target=payload.target,
                rr=payload.rr
            ))
            
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "status": "success",
                    "message": "Signal received and queued for processing",
                    "signal_id": payload.signal_id,
                    "timestamp": datetime.utcnow().isoformat()
                })
            }
        else:
            # Signal already exists (idempotency)
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "status": "duplicate",
                    "message": "Signal already processed",
                    "signal_id": payload.signal_id,
                    "timestamp": datetime.utcnow().isoformat()
                })
            }
    
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": f"Processing error: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            })
        }