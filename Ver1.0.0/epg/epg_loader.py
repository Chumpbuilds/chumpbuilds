"""
EPG Loader Thread
Background thread for loading EPG data with caching
"""

from PyQt6.QtCore import QThread, pyqtSignal
from typing import Dict
from datetime import datetime

class EPGLoaderThread(QThread):
    """Thread for loading EPG data in background"""
    epg_loaded = pyqtSignal(dict)
    
    def __init__(self, api, stream_id: str, epg_cache=None):
        super().__init__()
        self.api = api
        self.stream_id = stream_id
        self.epg_cache = epg_cache
    
    def run(self):
        """Load EPG data with cache support"""
        try:
            # Check cache first
            if self.epg_cache:
                cached_data = self.epg_cache.get(self.stream_id)
                if cached_data:
                    print(f"[EPG Loader] Using cached data for stream {self.stream_id}")
                    self.epg_loaded.emit({
                        'stream_id': self.stream_id,
                        'epg': cached_data,
                        'cached': True,
                        'timestamp': datetime.now()
                    })
                    return
            
            # Fetch from API
            print(f"[EPG Loader] Fetching from API for stream {self.stream_id}")
            
            # Try getting short EPG first
            epg_data = self.api.get_short_epg(self.stream_id)
            if epg_data:
                print(f"[EPG Loader] Got short EPG data")
                if self.epg_cache:
                    self.epg_cache.set(self.stream_id, epg_data)
                
                self.epg_loaded.emit({
                    'stream_id': self.stream_id,
                    'epg': epg_data,
                    'cached': False,
                    'timestamp': datetime.now()
                })
                return
            
            # Try alternative EPG method
            epg_list = self.api.get_simple_data_table(self.stream_id)
            if epg_list:
                print(f"[EPG Loader] Got simple data table")
                epg_data = {'epg_listings': epg_list}
                if self.epg_cache:
                    self.epg_cache.set(self.stream_id, epg_data)
                
                self.epg_loaded.emit({
                    'stream_id': self.stream_id,
                    'epg': epg_data,
                    'cached': False,
                    'timestamp': datetime.now()
                })
                return
            
            # No EPG data found
            print(f"[EPG Loader] No EPG data found for stream {self.stream_id}")
            self.epg_loaded.emit({
                'stream_id': self.stream_id,
                'epg': {},
                'cached': False,
                'timestamp': datetime.now()
            })
            
        except Exception as e:
            print(f"[EPG Loader] Error loading EPG: {e}")
            import traceback
            traceback.print_exc()
            
            self.epg_loaded.emit({
                'stream_id': self.stream_id,
                'epg': {},
                'cached': False,
                'timestamp': datetime.now(),
                'error': str(e)
            })