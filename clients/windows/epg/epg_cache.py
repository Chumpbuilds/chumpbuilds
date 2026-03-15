"""
EPG Cache Manager
Caches EPG data with 24-hour TTL to reduce API calls
"""

from datetime import datetime, timedelta
from typing import Dict, Optional
import json
import os

class EPGCache:
    """
    EPG cache with 24-hour TTL (Time To Live)
    
    Cache structure:
    {
        'stream_id': {
            'data': {...},
            'timestamp': datetime,
            'expires_at': datetime
        }
    }
    """
    
    def __init__(self, ttl_hours: int = 24, cache_dir: str = None):
        """
        Initialize EPG cache
        
        Args:
            ttl_hours: Time to live for cached EPG data (default: 24 hours)
            cache_dir: Optional directory to persist cache to disk
        """
        self.ttl_hours = ttl_hours
        self.cache: Dict[str, Dict] = {}
        self.cache_dir = cache_dir
        
        # Load from disk if cache directory specified
        if self.cache_dir:
            self._load_from_disk()
        
        print(f"[EPG Cache] Initialized with {ttl_hours} hour TTL")
    
    def get(self, stream_id: str) -> Optional[Dict]:
        """
        Get EPG data from cache if available and not expired
        
        Args:
            stream_id: Channel stream ID
            
        Returns:
            Cached EPG data or None if not found/expired
        """
        if stream_id not in self.cache:
            print(f"[EPG Cache] Miss for stream_id: {stream_id} (not in cache)")
            return None
        
        cached_item = self.cache[stream_id]
        expires_at = cached_item.get('expires_at')
        
        # Check if expired
        if expires_at and datetime.now() > expires_at:
            time_diff = datetime.now() - expires_at
            print(f"[EPG Cache] Expired for stream_id: {stream_id} (expired {time_diff} ago)")
            del self.cache[stream_id]
            return None
        
        # Show time until expiration
        time_remaining = expires_at - datetime.now()
        hours_remaining = time_remaining.total_seconds() / 3600
        print(f"[EPG Cache] Hit for stream_id: {stream_id} ({hours_remaining:.1f} hours remaining)")
        return cached_item.get('data')
    
    def set(self, stream_id: str, epg_data: Dict):
        """
        Store EPG data in cache
        
        Args:
            stream_id: Channel stream ID
            epg_data: EPG data to cache
        """
        now = datetime.now()
        expires_at = now + timedelta(hours=self.ttl_hours)
        
        self.cache[stream_id] = {
            'data': epg_data,
            'timestamp': now,
            'expires_at': expires_at
        }
        
        print(f"[EPG Cache] Stored stream_id: {stream_id} (expires at {expires_at.strftime('%Y-%m-%d %H:%M:%S')})")
        
        # Save to disk if enabled
        if self.cache_dir:
            self._save_to_disk()
    
    def clear(self, stream_id: Optional[str] = None):
        """
        Clear cache for specific stream or all streams
        
        Args:
            stream_id: Optional stream ID to clear. If None, clears all cache
        """
        if stream_id:
            if stream_id in self.cache:
                del self.cache[stream_id]
                print(f"[EPG Cache] Cleared stream_id: {stream_id}")
                if self.cache_dir:
                    self._save_to_disk()
        else:
            self.cache.clear()
            print("[EPG Cache] Cleared all cache")
            if self.cache_dir:
                self._save_to_disk()
    
    def cleanup_expired(self):
        """Remove all expired entries from cache"""
        now = datetime.now()
        expired_keys = []
        
        for stream_id, cached_item in self.cache.items():
            expires_at = cached_item.get('expires_at')
            if expires_at and now > expires_at:
                expired_keys.append(stream_id)
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            print(f"[EPG Cache] Cleaned up {len(expired_keys)} expired entries")
            if self.cache_dir:
                self._save_to_disk()
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        total = len(self.cache)
        now = datetime.now()
        expired = 0
        oldest_expiry = None
        newest_expiry = None
        
        for item in self.cache.values():
            expires_at = item.get('expires_at')
            if expires_at:
                if now > expires_at:
                    expired += 1
                else:
                    if not oldest_expiry or expires_at < oldest_expiry:
                        oldest_expiry = expires_at
                    if not newest_expiry or expires_at > newest_expiry:
                        newest_expiry = expires_at
        
        active = total - expired
        
        stats = {
            'total_entries': total,
            'active_entries': active,
            'expired_entries': expired,
            'ttl_hours': self.ttl_hours
        }
        
        if oldest_expiry:
            stats['next_expiry'] = oldest_expiry.strftime('%Y-%m-%d %H:%M:%S')
            stats['hours_until_next_expiry'] = (oldest_expiry - now).total_seconds() / 3600
        
        if newest_expiry:
            stats['last_expiry'] = newest_expiry.strftime('%Y-%m-%d %H:%M:%S')
        
        return stats
    
    def _load_from_disk(self):
        """Load cache from disk (if cache directory exists)"""
        if not self.cache_dir:
            return
        
        try:
            # Create directory if it doesn't exist
            os.makedirs(self.cache_dir, exist_ok=True)
            
            cache_file = os.path.join(self.cache_dir, 'epg_cache.json')
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    disk_cache = json.load(f)
                
                # Convert string timestamps back to datetime
                loaded_count = 0
                for stream_id, data in disk_cache.items():
                    try:
                        timestamp = datetime.fromisoformat(data['timestamp'])
                        expires_at = datetime.fromisoformat(data['expires_at'])
                        
                        # Only load if not expired
                        if datetime.now() < expires_at:
                            self.cache[stream_id] = {
                                'data': data['data'],
                                'timestamp': timestamp,
                                'expires_at': expires_at
                            }
                            loaded_count += 1
                    except Exception as e:
                        print(f"[EPG Cache] Error loading entry {stream_id}: {e}")
                        continue
                
                print(f"[EPG Cache] Loaded {loaded_count} valid entries from disk (skipped {len(disk_cache) - loaded_count} expired)")
        except Exception as e:
            print(f"[EPG Cache] Error loading from disk: {e}")
    
    def _save_to_disk(self):
        """Save cache to disk"""
        if not self.cache_dir:
            return
        
        try:
            # Create directory if it doesn't exist
            os.makedirs(self.cache_dir, exist_ok=True)
            
            # Convert datetime to string for JSON serialization
            disk_cache = {}
            for sid, data in self.cache.items():
                try:
                    disk_cache[sid] = {
                        'data': data['data'],
                        'timestamp': data['timestamp'].isoformat(),
                        'expires_at': data['expires_at'].isoformat()
                    }
                except Exception as e:
                    print(f"[EPG Cache] Error serializing entry {sid}: {e}")
                    continue
            
            cache_file = os.path.join(self.cache_dir, 'epg_cache.json')
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(disk_cache, f, indent=2)
            
            print(f"[EPG Cache] Saved {len(disk_cache)} entries to disk")
        except Exception as e:
            print(f"[EPG Cache] Error saving to disk: {e}")