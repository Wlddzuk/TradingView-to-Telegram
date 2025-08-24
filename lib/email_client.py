"""
IMAP Email Client for TradingView-to-Telegram Signal Bot
Polls Gmail for structured TradingView alert messages
"""

import email
import imaplib
import re
import ssl
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

from lib.config import settings

logger = logging.getLogger(__name__)

class EmailClient:
    """Gmail IMAP client for processing TradingView email alerts"""
    
    def __init__(self):
        self.imap_server = "imap.gmail.com"
        self.imap_port = 993
        self.email_user = settings.gmail_email
        self.email_password = settings.gmail_app_password
        self.folder_name = settings.gmail_folder_name
        self.connection = None
    
    def connect(self) -> bool:
        """Connect to Gmail IMAP server"""
        try:
            # Create SSL context
            context = ssl.create_default_context()
            
            # Connect to Gmail IMAP
            self.connection = imaplib.IMAP4_SSL(self.imap_server, self.imap_port, ssl_context=context)
            self.connection.login(self.email_user, self.email_password)
            
            logger.info(f"Connected to Gmail IMAP for {self.email_user}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Gmail: {e}")
            self.connection = None
            return False
    
    def disconnect(self):
        """Disconnect from IMAP server"""
        if self.connection:
            try:
                self.connection.close()
                self.connection.logout()
            except:
                pass
            self.connection = None
    
    def get_recent_signals(self, minutes_back: int = 5) -> List[Dict[str, Any]]:
        """
        Get recent TradingView signal emails from the specified folder
        
        Args:
            minutes_back: How many minutes back to search for emails
            
        Returns:
            List of parsed signal dictionaries
        """
        if not self.connection:
            if not self.connect():
                return []
        
        try:
            # Select the TradingView folder
            status, messages = self.connection.select(self.folder_name)
            if status != 'OK':
                logger.error(f"Failed to select folder {self.folder_name}")
                return []
            
            # Calculate search date (X minutes ago)
            cutoff_time = datetime.utcnow() - timedelta(minutes=minutes_back)
            search_date = cutoff_time.strftime('%d-%b-%Y')
            
            # Search for recent emails from TradingView
            search_criteria = f'(FROM "noreply@tradingview.com" SINCE "{search_date}")'
            status, message_ids = self.connection.search(None, search_criteria)
            
            if status != 'OK':
                logger.error(f"Email search failed: {status}")
                return []
            
            email_ids = message_ids[0].split()
            if not email_ids:
                logger.debug("No recent TradingView emails found")
                return []
            
            signals = []
            
            # Process recent emails (limit to last 20 for performance)
            for email_id in email_ids[-20:]:
                try:
                    signal = self._process_email(email_id)
                    if signal:
                        signals.append(signal)
                except Exception as e:
                    logger.error(f"Error processing email {email_id}: {e}")
                    continue
            
            logger.info(f"Found {len(signals)} valid signals in {len(email_ids)} emails")
            return signals
            
        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            return []
    
    def _process_email(self, email_id: bytes) -> Optional[Dict[str, Any]]:
        """
        Process a single email and extract structured signal data
        
        Args:
            email_id: Email ID from IMAP search
            
        Returns:
            Parsed signal dictionary or None if invalid
        """
        try:
            # Fetch email content
            status, msg_data = self.connection.fetch(email_id, '(RFC822)')
            if status != 'OK':
                return None
            
            # Parse email
            email_body = msg_data[0][1]
            email_message = email.message_from_bytes(email_body)
            
            # Extract email metadata
            subject = email_message['Subject'] or ''
            sender = email_message['From'] or ''
            date_received = email.utils.parsedate_to_datetime(email_message['Date'])
            
            # Only process TradingView emails
            if 'tradingview.com' not in sender.lower():
                return None
            
            # Get email body content
            body = self._get_email_body(email_message)
            if not body:
                return None
            
            # Parse structured signal data
            signal_data = self._parse_signal_content(body)
            if not signal_data:
                return None
            
            # Add metadata
            signal_data.update({
                'email_subject': subject,
                'email_sender': sender,
                'email_received_at': date_received.isoformat(),
                'processed_at': datetime.utcnow().isoformat()
            })
            
            return signal_data
            
        except Exception as e:
            logger.error(f"Error processing email {email_id}: {e}")
            return None
    
    def _get_email_body(self, email_message) -> Optional[str]:
        """Extract text body from email message"""
        try:
            if email_message.is_multipart():
                for part in email_message.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True)
                        if isinstance(body, bytes):
                            body = body.decode('utf-8')
                        return body
            else:
                body = email_message.get_payload(decode=True)
                if isinstance(body, bytes):
                    body = body.decode('utf-8')
                return body
        except Exception as e:
            logger.error(f"Error extracting email body: {e}")
        
        return None
    
    def _parse_signal_content(self, body: str) -> Optional[Dict[str, Any]]:
        """
        Parse structured signal content from email body
        
        Expected format: action:ENTRY|symbol:ETHUSDT|tf:60|entry:4787.12|stop:4720.45|target:4987.13|rr:3|signal_id:ETHUSDT_60_1734567890000|secret:walid-ema-bounce-2025
        
        Args:
            body: Email body text
            
        Returns:
            Parsed signal dictionary or None if invalid format
        """
        try:
            # Find the structured signal line
            signal_pattern = r'action:ENTRY\|([^|\n]+)'
            match = re.search(signal_pattern, body)
            
            if not match:
                logger.debug("No structured signal pattern found in email")
                return None
            
            # Extract the full signal line
            signal_line_match = re.search(r'action:ENTRY\|[^|\n]*(?:\|[^|\n]*)*', body)
            if not signal_line_match:
                return None
            
            signal_line = signal_line_match.group(0)
            
            # Parse key:value pairs
            pairs = signal_line.split('|')
            signal_data = {}
            
            for pair in pairs:
                if ':' in pair:
                    key, value = pair.split(':', 1)
                    signal_data[key.strip()] = value.strip()
            
            # Validate required fields
            required_fields = ['action', 'symbol', 'tf', 'entry', 'stop', 'target', 'rr', 'signal_id', 'secret']
            for field in required_fields:
                if field not in signal_data:
                    logger.warning(f"Missing required field {field} in signal data")
                    return None
            
            # Validate secret
            if signal_data.get('secret') != 'walid-ema-bounce-2025':
                logger.warning(f"Invalid secret in signal: {signal_data.get('secret')}")
                return None
            
            # Convert numeric fields
            try:
                signal_data['entry'] = float(signal_data['entry'])
                signal_data['stop'] = float(signal_data['stop'])
                signal_data['target'] = float(signal_data['target'])
                signal_data['rr'] = float(signal_data['rr'])
                if 'bar_time' in signal_data:
                    signal_data['bar_time'] = int(signal_data['bar_time'])
            except ValueError as e:
                logger.error(f"Error converting numeric fields: {e}")
                return None
            
            # Add event field for compatibility with existing code
            signal_data['event'] = 'EMA_BOUNCE_BUY'
            
            logger.info(f"Parsed signal: {signal_data['symbol']} {signal_data['tf']} @ {signal_data['entry']}")
            return signal_data
            
        except Exception as e:
            logger.error(f"Error parsing signal content: {e}")
            return None
    
    def mark_as_processed(self, email_id: bytes):
        """Mark email as processed (move to processed folder or flag)"""
        try:
            # Add a flag to mark as processed
            self.connection.store(email_id, '+FLAGS', '\\Seen')
            logger.debug(f"Marked email {email_id} as processed")
        except Exception as e:
            logger.error(f"Error marking email as processed: {e}")

# Global email client instance
email_client = None

def get_email_client() -> EmailClient:
    """Get or create global email client instance"""
    global email_client
    if email_client is None:
        email_client = EmailClient()
    return email_client