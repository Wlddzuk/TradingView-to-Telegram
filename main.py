"""
TradingView-to-Telegram Signal Bot
FastAPI server that receives webhook alerts and forwards to Telegram
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from database import init_database, close_database
from webhook_handler import router as webhook_router
from telegram_handlers import setup_telegram_bot


# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    logger.info("Starting TradingView-to-Telegram Signal Bot")
    await init_database()
    await setup_telegram_bot()
    logger.info("Bot startup completed")
    
    yield
    
    # Shutdown
    logger.info("Shutting down bot")
    await close_database()
    logger.info("Bot shutdown completed")


# Create FastAPI app
app = FastAPI(
    title="TradingView-to-Telegram Signal Bot",
    description="Receives webhook alerts from TradingView and forwards formatted signals to Telegram",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Include webhook router
app.include_router(webhook_router, prefix="/api/v1")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests"""
    start_time = datetime.utcnow()
    
    # Log request
    logger.info(
        "http_request_started",
        method=request.method,
        url=str(request.url),
        user_agent=request.headers.get("user-agent"),
        remote_addr=request.client.host if request.client else None
    )
    
    response = await call_next(request)
    
    # Calculate processing time
    process_time = (datetime.utcnow() - start_time).total_seconds() * 1000
    
    # Log response
    logger.info(
        "http_request_completed",
        method=request.method,
        url=str(request.url),
        status_code=response.status_code,
        process_time_ms=round(process_time, 2)
    )
    
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(
        "unhandled_exception",
        exception=str(exc),
        exception_type=type(exc).__name__,
        url=str(request.url),
        method=request.method
    )
    
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "timestamp": datetime.utcnow().isoformat()}
    )


@app.get("/healthz")
async def health_check():
    """Basic liveness check"""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "tradingview-telegram-bot"
    }


@app.get("/readyz")
async def readiness_check():
    """Comprehensive readiness check"""
    from database import test_database_connection
    from telegram_bot import test_telegram_connection
    
    checks = {
        "database": "unknown",
        "telegram": "unknown"
    }
    
    # Test database connection
    try:
        await test_database_connection()
        checks["database"] = "connected"
    except Exception as e:
        logger.error("database_health_check_failed", error=str(e))
        checks["database"] = "failed"
    
    # Test Telegram connection
    try:
        await test_telegram_connection()
        checks["telegram"] = "reachable"
    except Exception as e:
        logger.error("telegram_health_check_failed", error=str(e))
        checks["telegram"] = "failed"
    
    # Determine overall status
    all_healthy = all(status in ["connected", "reachable"] for status in checks.values())
    
    response = {
        "status": "ready" if all_healthy else "not_ready",
        "timestamp": datetime.utcnow().isoformat(),
        **checks
    }
    
    status_code = 200 if all_healthy else 503
    return JSONResponse(content=response, status_code=status_code)


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "TradingView-to-Telegram Signal Bot",
        "version": "1.0.0",
        "description": "Receives webhook alerts from TradingView EMA Bounce strategy and forwards to Telegram",
        "endpoints": {
            "health": "/healthz",
            "readiness": "/readyz",
            "webhook": "/api/v1/tv-webhook"
        },
        "supported_pairs": settings.default_pairs,
        "supported_timeframes": settings.supported_timeframes,
        "timezone": settings.tz_display
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )