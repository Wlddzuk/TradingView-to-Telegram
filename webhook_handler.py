"""
TradingView webhook handler for EMA Bounce strategy signals
"""

import secrets
from datetime import datetime
from typing import Any, Dict

import structlog
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field, validator

from config import settings
from database import save_signal, get_enabled_pairs

logger = structlog.get_logger()

router = APIRouter()

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

async def verify_shared_secret(request: Request) -> bool:
    """Verify TradingView shared secret from headers"""
    tv_secret = request.headers.get("X-TV-Secret")
    
    if not tv_secret:
        logger.warning("Missing X-TV-Secret header", client_ip=request.client.host)
        return False
    
    # Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(tv_secret, settings.tv_shared_secret):
        logger.warning("Invalid shared secret", client_ip=request.client.host)
        return False
    
    return True

async def verify_symbol_allowed(symbol: str) -> bool:
    """Check if symbol is in allowed pairs list"""
    enabled_pairs = await get_enabled_pairs()
    if symbol not in enabled_pairs:
        logger.warning("Symbol not in enabled pairs", symbol=symbol, enabled_pairs=enabled_pairs)
        return False
    return True

@router.post("/tv-webhook")
async def receive_tradingview_webhook(
    payload: TradingViewPayload,
    request: Request
):
    """
    Receive and process TradingView webhook alerts
    """
    client_ip = request.client.host if request.client else "unknown"
    
    logger.info(
        "webhook_received",
        signal_id=payload.signal_id,
        symbol=payload.symbol,
        timeframe=payload.timeframe,
        event=payload.event,
        client_ip=client_ip
    )
    
    try:
        # Verify shared secret
        if not await verify_shared_secret(request):
            raise HTTPException(
                status_code=401,
                detail="Unauthorized: Invalid or missing shared secret"
            )
        
        # Verify symbol is allowed
        if not await verify_symbol_allowed(payload.symbol):
            raise HTTPException(
                status_code=400,
                detail=f"Symbol {payload.symbol} is not in enabled pairs list"
            )
        
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
            logger.info(
                "webhook_processed_successfully",
                signal_id=payload.signal_id,
                symbol=payload.symbol,
                timeframe=payload.timeframe
            )
            
            # Queue for Telegram processing (will be handled by background task)
            await queue_telegram_message(payload)
            
            return {
                "status": "success",
                "message": "Signal received and queued for processing",
                "signal_id": payload.signal_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            # Signal already exists (idempotency)
            logger.info(
                "webhook_duplicate_signal",
                signal_id=payload.signal_id,
                symbol=payload.symbol,
                timeframe=payload.timeframe
            )
            
            return {
                "status": "duplicate",
                "message": "Signal already processed",
                "signal_id": payload.signal_id,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    except HTTPException:
        # Re-raise HTTP exceptions (auth, validation errors)
        raise
    
    except Exception as e:
        logger.error(
            "webhook_processing_error",
            signal_id=payload.signal_id,
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            error=str(e),
            client_ip=client_ip
        )
        
        raise HTTPException(
            status_code=500,
            detail="Internal server error processing webhook"
        )

async def queue_telegram_message(payload: TradingViewPayload):
    """Queue signal for Telegram processing"""
    try:
        # Import here to avoid circular imports
        from telegram_bot import send_signal_message
        
        # Send message asynchronously (fire and forget)
        import asyncio
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
        
        logger.info(
            "telegram_message_queued",
            signal_id=payload.signal_id,
            symbol=payload.symbol,
            timeframe=payload.timeframe
        )
        
    except Exception as e:
        logger.error(
            "failed_to_queue_telegram_message",
            signal_id=payload.signal_id,
            error=str(e)
        )

@router.get("/webhook-test")
async def webhook_test():
    """Test endpoint to verify webhook handler is working"""
    return {
        "status": "ok",
        "message": "Webhook handler is operational",
        "supported_symbols": await get_enabled_pairs(),
        "supported_timeframes": settings.timeframes_list,
        "timestamp": datetime.utcnow().isoformat()
    }