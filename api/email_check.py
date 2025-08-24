# api/email_check.py - Complete Email Processing for Vercel Serverless
from http.server import BaseHTTPRequestHandler
import json, os, re, imaplib, email, ssl, asyncio, threading
from datetime import datetime
from typing import Optional, Dict, Any, List

REQUIRED_KEYS = [
    "GMAIL_EMAIL", 
    "GMAIL_APP_PASSWORD",
    "GMAIL_FOLDER_NAME",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID_DEFAULT",
    "TV_SHARED_SECRET",
]

class EmailProcessor:
    def __init__(self):
        self.gmail_email = os.environ.get("GMAIL_EMAIL", "")
        self.gmail_password = os.environ.get("GMAIL_APP_PASSWORD", "")
        self.folder_name = os.environ.get("GMAIL_FOLDER_NAME", "TradingView")
        self.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID_DEFAULT", "")
        
    def check_emails(self) -> Dict[str, Any]:
        """Check Gmail for new TradingView signal emails"""
        try:
            # Connect to Gmail IMAP
            context = ssl.create_default_context()
            mail = imaplib.IMAP4_SSL("imap.gmail.com", 993, ssl_context=context)
            mail.login(self.gmail_email, self.gmail_password)
            
            # Select the TradingView folder
            result = mail.select(f'"{self.folder_name}"')
            if result[0] != 'OK':
                return {"status": "error", "message": f"Cannot access folder '{self.folder_name}'"}
            
            # Search for unseen emails
            result, data = mail.search(None, 'UNSEEN')
            if result != 'OK':
                return {"status": "error", "message": "Failed to search for emails"}
                
            email_ids = data[0].split()
            
            if not email_ids:
                return {
                    "status": "ok",
                    "message": "No new signals found", 
                    "signals_processed": 0,
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Process each email
            processed_signals = []
            successful = 0
            failed = 0
            
            for email_id in email_ids:
                try:
                    # Fetch email
                    result, msg_data = mail.fetch(email_id, '(RFC822)')
                    if result != 'OK':
                        continue
                        
                    # Parse email
                    raw_email = msg_data[0][1]
                    email_message = email.message_from_bytes(raw_email)
                    
                    # Extract body
                    body = self._extract_email_body(email_message)
                    if not body:
                        continue
                    
                    # Parse signal data
                    signal_data = self._parse_signal_content(body)
                    if signal_data:
                        # Process signal
                        result = self._process_signal(signal_data)
                        processed_signals.append(result)
                        
                        if result["status"] == "success":
                            successful += 1
                        else:
                            failed += 1
                    
                    # Mark as read
                    mail.store(email_id, '+FLAGS', '\\Seen')
                    
                except Exception as e:
                    failed += 1
                    processed_signals.append({
                        "status": "error",
                        "error": str(e),
                        "email_id": email_id.decode()
                    })
            
            mail.close()
            mail.logout()
            
            return {
                "status": "ok",
                "message": f"Processed {len(processed_signals)} signals",
                "signals_processed": len(processed_signals),
                "successful": successful,
                "failed": failed,
                "results": processed_signals,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error", 
                "message": f"IMAP connection failed: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def _extract_email_body(self, email_message) -> Optional[str]:
        """Extract plain text body from email message"""
        try:
            if email_message.is_multipart():
                for part in email_message.walk():
                    if part.get_content_type() == "text/plain":
                        return part.get_payload(decode=True).decode('utf-8')
            else:
                return email_message.get_payload(decode=True).decode('utf-8')
        except:
            return None
    
    def _parse_signal_content(self, body: str) -> Optional[Dict[str, Any]]:
        """Parse structured signal data from email body"""
        try:
            # Look for signal pattern: action:ENTRY|symbol:...|tf:...|...
            signal_pattern = r'action:ENTRY\|([^|\n]+)'
            match = re.search(signal_pattern, body)
            
            if not match:
                return None
            
            # Extract the signal line
            signal_line = "action:ENTRY|" + match.group(1)
            
            # Parse pipe-delimited data
            pairs = signal_line.split('|')
            signal_data = {}
            
            for pair in pairs:
                if ':' in pair:
                    key, value = pair.split(':', 1)
                    signal_data[key.strip()] = value.strip()
            
            # Validate required fields
            required_fields = ['action', 'symbol', 'tf', 'entry', 'stop', 'target', 'rr', 'signal_id']
            if not all(field in signal_data for field in required_fields):
                return None
            
            # Convert to expected format
            return {
                "event": "EMA_BOUNCE_BUY",
                "symbol": signal_data['symbol'],
                "timeframe": signal_data['tf'], 
                "bar_time": int(datetime.utcnow().timestamp() * 1000),  # Use current time
                "entry": float(signal_data['entry']),
                "stop": float(signal_data['stop']),
                "target": float(signal_data['target']),
                "rr": float(signal_data['rr']),
                "signal_id": signal_data['signal_id']
            }
            
        except Exception as e:
            return None
    
    def _process_signal(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process validated signal - send to Telegram"""
        try:
            # Format Telegram message
            message = self._format_telegram_message(signal_data)
            
            # Send to Telegram (simplified version for serverless)
            import urllib.request
            import urllib.parse
            
            telegram_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            params = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }
            
            data = urllib.parse.urlencode(params).encode()
            req = urllib.request.Request(telegram_url, data=data)
            
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    return {
                        "status": "success",
                        "signal_id": signal_data["signal_id"],
                        "symbol": signal_data["symbol"],
                        "timeframe": signal_data["timeframe"],
                        "entry": signal_data["entry"],
                        "telegram_sent": True
                    }
                else:
                    return {
                        "status": "telegram_error",
                        "signal_id": signal_data["signal_id"], 
                        "error": f"Telegram API error: {response.status}"
                    }
        
        except Exception as e:
            return {
                "status": "error",
                "signal_id": signal_data.get("signal_id", "unknown"),
                "error": f"Processing error: {str(e)}"
            }
    
    def _format_telegram_message(self, signal: Dict[str, Any]) -> str:
        """Format signal as Telegram message"""
        symbol = signal["symbol"]
        timeframe_map = {"15": "15m", "60": "1h", "240": "4h", "D": "1d"}
        tf_display = timeframe_map.get(signal["timeframe"], signal["timeframe"])
        
        # Determine quote currency and format prices
        if symbol.endswith('USDT'):
            entry_str = f"${signal['entry']:,.2f}"
            stop_str = f"${signal['stop']:,.2f}" 
            target_str = f"${signal['target']:,.2f}"
        elif symbol.endswith('BTC'):
            entry_str = f"{signal['entry']:.8f} BTC"
            stop_str = f"{signal['stop']:.8f} BTC"
            target_str = f"{signal['target']:.8f} BTC"
        else:
            entry_str = f"{signal['entry']}"
            stop_str = f"{signal['stop']}"
            target_str = f"{signal['target']}"
        
        # Calculate risk percentage
        risk_pct = abs(signal['entry'] - signal['stop']) / signal['entry'] * 100
        
        return f"""🚀 **EMA BOUNCE SIGNAL** 🚀

💰 **COIN PAIR**: {symbol.replace('USDT', '/USDT').replace('BTC', '/BTC')}
⏰ **TIMEFRAME**: {tf_display}
📅 **Signal Time**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

📈 **TRADE DETAILS**:
🔵 **ENTRY**: {entry_str}
🔴 **STOP LOSS**: {stop_str}
🟢 **TAKE PROFIT**: {target_str}

📊 **RISK METRICS**:
💸 **Risk**: {risk_pct:.2f}% (Entry to Stop)
🎯 **Reward**: {signal['rr']}R ({signal['rr']}:1 Risk/Reward)

🆔 Signal ID: {signal['signal_id']}"""

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Check if all required environment variables are set
        missing = [k for k in REQUIRED_KEYS if not os.environ.get(k)]
        
        if missing:
            payload = {
                "ok": False,
                "missing": missing,
                "message": "Missing required environment variables",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            # Process emails
            processor = EmailProcessor()
            payload = processor.check_emails()
        
        body = json.dumps(payload).encode("utf-8")
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json") 
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)