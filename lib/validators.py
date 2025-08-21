"""
Simple payload validation for TradingView webhooks
"""

def validate_tradingview_payload(data):
    """Validate TradingView webhook payload"""
    
    required_fields = [
        'event', 'symbol', 'timeframe', 'bar_time', 
        'entry', 'stop', 'target', 'rr', 'signal_id'
    ]
    
    # Check required fields
    for field in required_fields:
        if field not in data:
            raise ValueError(f"Missing required field: {field}")
    
    # Validate types
    if not isinstance(data['entry'], (int, float)) or data['entry'] <= 0:
        raise ValueError("Entry price must be a positive number")
    
    if not isinstance(data['stop'], (int, float)) or data['stop'] <= 0:
        raise ValueError("Stop price must be a positive number")
    
    if not isinstance(data['target'], (int, float)) or data['target'] <= 0:
        raise ValueError("Target price must be a positive number")
    
    # Validate long position logic
    if data['stop'] >= data['entry']:
        raise ValueError("Stop loss must be below entry price for long positions")
    
    if data['target'] <= data['entry']:
        raise ValueError("Target must be above entry price for long positions")
    
    # Validate event type
    if data['event'] not in ['EMA_BOUNCE_BUY']:
        raise ValueError(f"Invalid event type: {data['event']}")
    
    # Normalize symbol
    data['symbol'] = data['symbol'].upper().strip()
    
    return data