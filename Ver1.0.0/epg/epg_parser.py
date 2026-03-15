"""
EPG Parser
Cleans and parses EPG data from various formats
"""

import html
from datetime import datetime
from typing import Dict, List, Optional

def clean_text(text: str) -> str:
    """
    Clean and decode text from EPG data
    
    Args:
        text: Raw text from EPG
        
    Returns:
        Cleaned text or empty string if garbled
    """
    if not text or not isinstance(text, str):
        return ""
    
    try:
        # Decode HTML entities
        text = html.unescape(text)
        
        # Try to fix common encoding issues
        if all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=' 
               for c in text.replace('\n', '').replace(' ', '')):
            try:
                import base64
                decoded = base64.b64decode(text).decode('utf-8', errors='ignore')
                if decoded and len(decoded) > 3:
                    text = decoded
            except:
                pass
        
        # Remove excessive whitespace
        text = ' '.join(text.split())
        
        # Remove non-printable characters except newlines
        text = ''.join(char for char in text if char.isprintable() or char == '\n')
        
        # Detect garbled text (too many consonants in a row)
        if len(text) > 20:
            consonant_count = 0
            max_consonants = 0
            for char in text.lower():
                if char in 'bcdfghjklmnpqrstvwxyz':
                    consonant_count += 1
                    max_consonants = max(max_consonants, consonant_count)
                else:
                    consonant_count = 0
            
            # If we have more than 7 consonants in a row, text is probably garbled
            if max_consonants > 7:
                return ""
        
        return text.strip()
    except Exception as e:
        print(f"[EPG Parser] Error cleaning text: {e}")
        return ""

class EPGParser:
    """Parse EPG data from different formats"""
    
    @staticmethod
    def parse_epg_response(epg_data: Dict) -> List[Dict]:
        """
        Parse EPG response into standardized format
        
        Args:
            epg_data: Raw EPG data from API
            
        Returns:
            List of parsed EPG entries
        """
        if not epg_data:
            return []
        
        epg_listings = []
        
        if isinstance(epg_data, dict):
            if 'epg_listings' in epg_data:
                epg_listings = epg_data['epg_listings']
            else:
                # EPG data might be keyed by timestamps or IDs
                for key, value in epg_data.items():
                    if isinstance(value, dict):
                        epg_listings.append(value)
                    elif isinstance(value, list):
                        epg_listings.extend(value)
        elif isinstance(epg_data, list):
            epg_listings = epg_data
        
        # Clean and standardize each entry
        cleaned_listings = []
        for entry in epg_listings:
            if isinstance(entry, dict):
                cleaned_entry = EPGParser.clean_epg_entry(entry)
                if cleaned_entry:
                    cleaned_listings.append(cleaned_entry)
        
        # Sort by start time
        try:
            cleaned_listings.sort(key=lambda x: x.get('start_timestamp', 0))
        except:
            pass
        
        return cleaned_listings
    
    @staticmethod
    def clean_epg_entry(entry: Dict) -> Optional[Dict]:
        """
        Clean and standardize a single EPG entry
        
        Args:
            entry: Raw EPG entry
            
        Returns:
            Cleaned EPG entry or None if invalid
        """
        title = clean_text(entry.get('title', entry.get('name', '')))
        
        # Skip if no valid title
        if not title or len(title) < 2:
            return None
        
        description = clean_text(entry.get('description', entry.get('desc', '')))
        
        # Parse start/end times
        start_time = entry.get('start', entry.get('start_timestamp'))
        end_time = entry.get('end', entry.get('stop', entry.get('stop_timestamp')))
        
        start_dt = EPGParser.parse_time(start_time)
        end_dt = EPGParser.parse_time(end_time)
        
        return {
            'title': title,
            'description': description,
            'start': start_time,
            'end': end_time,
            'start_datetime': start_dt,
            'end_datetime': end_dt,
            'start_timestamp': int(start_dt.timestamp()) if start_dt else 0,
            'end_timestamp': int(end_dt.timestamp()) if end_dt else 0,
            'is_current': EPGParser.is_currently_airing(start_dt, end_dt),
            'raw_data': entry
        }
    
    @staticmethod
    def parse_time(time_value) -> Optional[datetime]:
        """
        Parse time from various formats
        
        Args:
            time_value: Time as timestamp, string, or datetime
            
        Returns:
            Parsed datetime or None
        """
        if not time_value:
            return None
        
        try:
            # If already datetime
            if isinstance(time_value, datetime):
                return time_value
            
            # If timestamp
            if isinstance(time_value, (int, float)):
                return datetime.fromtimestamp(time_value)
            
            # If string, try various formats
            if isinstance(time_value, str):
                formats = [
                    '%Y-%m-%d %H:%M:%S',
                    '%Y%m%d%H%M%S',
                    '%H:%M:%S',
                    '%H:%M'
                ]
                
                for fmt in formats:
                    try:
                        return datetime.strptime(time_value, fmt)
                    except:
                        continue
        except Exception as e:
            print(f"[EPG Parser] Error parsing time '{time_value}': {e}")
        
        return None
    
    @staticmethod
    def is_currently_airing(start_dt: Optional[datetime], end_dt: Optional[datetime]) -> bool:
        """Check if program is currently airing"""
        if not start_dt or not end_dt:
            return False
        
        now = datetime.now()
        return start_dt <= now <= end_dt
    
    @staticmethod
    def format_time_range(start_dt: Optional[datetime], end_dt: Optional[datetime]) -> str:
        """Format time range as string"""
        if not start_dt or not end_dt:
            return "Time N/A"
        
        return f"{start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')}"