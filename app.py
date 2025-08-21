"""
Simple webhook receiver for TradingView to Telegram signals
"""

import json
import secrets
import asyncio
from datetime import datetime
from flask import Flask, request, jsonify

from lib.config import settings
from lib.database import save_signal, get_enabled_pairs
from lib.telegram_bot import send_signal_message
from lib.validators import validate_tradingview_payload

app = Flask(__name__)

@app.route('/api/webhook', methods=['POST'])
def webhook():
    """TradingView webhook endpoint"""
    
    try:
        # Verify shared secret
        tv_secret = request.headers.get("x-tv-secret") or request.headers.get("X-TV-Secret")
        
        if not tv_secret:
            return jsonify({"error": "Missing X-TV-Secret header"}), 401
        
        if not secrets.compare_digest(tv_secret, settings.tv_shared_secret):
            return jsonify({"error": "Invalid shared secret"}), 401
        
        # Parse JSON payload
        try:
            payload = request.get_json(force=True)
        except Exception:
            return jsonify({"error": "Invalid JSON payload"}), 400
        
        # Validate payload
        try:
            validated_payload = validate_tradingview_payload(payload)
        except Exception as e:
            return jsonify({"error": f"Validation error: {str(e)}"}), 400
        
        # Process webhook in background
        asyncio.run(process_signal(validated_payload))
        
        return jsonify({
            "status": "success",
            "message": "Signal received and processed",
            "signal_id": validated_payload.get("signal_id"),
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            "error": "Internal server error",
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@app.route('/api/health', methods=['GET'])
@app.route('/healthz', methods=['GET'])
@app.route('/', methods=['GET'])
def health():
    """Health check endpoint"""
    
    return jsonify({
        "status": "ok",
        "service": "TradingView-to-Telegram Signal Bot",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "webhook": "/api/webhook",
            "health": "/api/health"
        }
    })

async def process_signal(payload):
    """Process the validated signal"""
    
    try:
        # Save signal to database (with idempotency)
        signal_saved = await save_signal(
            signal_id=payload["signal_id"],
            symbol=payload["symbol"],
            timeframe=payload["timeframe"],
            event=payload["event"],
            bar_time=payload["bar_time"],
            entry=payload["entry"],
            stop=payload["stop"],
            target=payload["target"],
            rr=payload["rr"]
        )
        
        if signal_saved:
            # Send to Telegram
            await send_signal_message(
                signal_id=payload["signal_id"],
                symbol=payload["symbol"],
                timeframe=payload["timeframe"],
                event=payload["event"],
                bar_time=payload["bar_time"],
                entry=payload["entry"],
                stop=payload["stop"],
                target=payload["target"],
                rr=payload["rr"]
            )
    
    except Exception as e:
        print(f"Error processing signal: {e}")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)