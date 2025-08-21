"""
Vercel serverless function for health checks
"""

import json
from datetime import datetime
from urllib.parse import parse_qs

from lib.config import settings
from lib.database import test_database_connection, get_enabled_pairs
from lib.telegram_bot import test_telegram_connection

def handler(request):
    """Vercel serverless handler for health checks"""
    
    # Handle preflight OPTIONS request
    if request.method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        }
    
    # Only allow GET requests
    if request.method != "GET":
        return {
            "statusCode": 405,
            "body": json.dumps({"error": "Method not allowed"})
        }
    
    try:
        # Parse query parameters
        query_string = getattr(request, 'query_string', '') or ''
        if isinstance(query_string, bytes):
            query_string = query_string.decode()
        
        query_params = parse_qs(query_string)
        
        # Check for specific health check type
        if 'check' in query_params and query_params['check'][0] == 'ready':
            return handle_readiness_check()
        elif 'info' in query_params:
            return handle_info_request()
        else:
            return handle_liveness_check()
            
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Health check failed",
                "details": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
        }

def handle_liveness_check():
    """Basic liveness check"""
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "tradingview-telegram-bot"
        })
    }

def handle_readiness_check():
    """Comprehensive readiness check"""
    import asyncio
    
    # For Vercel, we need to handle async properly
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(run_readiness_checks())
        return result
    finally:
        loop.close()

async def run_readiness_checks():
    """Run async readiness checks"""
    checks = {
        "database": "unknown",
        "telegram": "unknown"
    }
    
    # Test database connection
    try:
        if settings.has_kv_config:
            await test_database_connection()
            checks["database"] = "connected"
        else:
            checks["database"] = "not_configured"
    except Exception:
        checks["database"] = "failed"
    
    # Test Telegram connection
    try:
        await test_telegram_connection()
        checks["telegram"] = "reachable"
    except Exception:
        checks["telegram"] = "failed"
    
    # Determine overall status
    all_healthy = all(status in ["connected", "reachable", "not_configured"] for status in checks.values())
    
    response_data = {
        "status": "ready" if all_healthy else "not_ready",
        "timestamp": datetime.utcnow().isoformat(),
        **checks
    }
    
    status_code = 200 if all_healthy else 503
    
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(response_data)
    }

def handle_info_request():
    """API information endpoint"""
    import asyncio
    
    # For Vercel, we need to handle async properly
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(get_api_info())
        return result
    finally:
        loop.close()

async def get_api_info():
    """Get API information"""
    try:
        enabled_pairs = await get_enabled_pairs()
    except Exception:
        enabled_pairs = settings.pairs_list
    
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "service": "TradingView-to-Telegram Signal Bot",
            "version": "1.0.0",
            "description": "Receives webhook alerts from TradingView EMA Bounce strategy and forwards to Telegram",
            "endpoints": {
                "health": "/api/health",
                "readiness": "/api/health?check=ready",
                "webhook": "/api/webhook"
            },
            "supported_pairs": enabled_pairs,
            "supported_timeframes": settings.timeframes_list,
            "timezone": settings.tz_display,
            "deployment": "vercel-serverless"
        })
    }