"""
Xtreme Codes API Authentication and Data Handler
Updated with improved connection handling and better compatibility
Current Date and Time (UTC): 2025-11-16 10:15:28
Current User: covchump
"""

import requests
import json
from datetime import datetime
from typing import Dict, Optional, List
import hashlib
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class XtremeCodesAPI:
    def __init__(self):
        self.base_url = None
        self.username = None
        self.password = None
        self.user_info = None
        self.server_info = None
        self.session = self._create_session()
        
    def _create_session(self):
        """Create a robust session with proper headers and retry logic"""
        session = requests.Session()
        
        # Add common headers that IPTV servers expect
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        })
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        # Mount adapters with retry strategy
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
        
    def login(self, url: str, username: str, password: str) -> Dict:
        """
        Authenticate with Xtreme Codes API with improved error handling
        
        Args:
            url: Server URL (without trailing slash)
            username: Account username
            password: Account password
            
        Returns:
            Dict containing user info and authentication status
        """
        # Clean URL
        url = url.rstrip('/')
        
        # Ensure URL has protocol
        if not url.startswith(('http://', 'https://')):
            # For c0vchump.com, default to http with port 80
            if 'c0vchump.com' in url:
                url = f'http://{url}'
                if ':' not in url.split('//')[-1]:  # Add port if not specified
                    url = f'{url}:80'
            else:
                url = f'http://{url}'
            
        self.base_url = url
        self.username = username
        self.password = password
        
        print(f"[API] Login attempt to: {self.base_url}")
        print(f"[API] Using enhanced session with proper headers")
        
        try:
            # Xtreme Codes API login endpoint
            login_url = f"{self.base_url}/player_api.php"
            params = {
                'username': username,
                'password': password
            }
            
            print(f"[API] Making request to: {login_url}")
            print(f"[API] Request params: username={username}, password=***")
            
            # Use longer timeout and better error handling
            response = self.session.get(
                login_url, 
                params=params, 
                timeout=(10, 30),  # (connect timeout, read timeout)
                allow_redirects=True
            )
            
            print(f"[API] Response status: {response.status_code}")
            print(f"[API] Response headers: {dict(response.headers)}")
            
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            print(f"[API] Content type: {content_type}")
            
            # Try to parse JSON
            try:
                data = response.json()
                print(f"[API] JSON response keys: {data.keys() if isinstance(data, dict) else 'Not a dict'}")
            except json.JSONDecodeError as e:
                print(f"[API] JSON decode error: {e}")
                print(f"[API] Raw response text (first 500 chars): {response.text[:500]}")
                return {
                    'success': False,
                    'message': f'Invalid JSON response from server: {str(e)}'
                }
            
            if data.get('user_info'):
                self.user_info = data['user_info']
                self.server_info = data.get('server_info', {})
                
                print(f"[API] ✅ Login successful for user: {self.user_info.get('username', 'Unknown')}")
                print(f"[API] User status: {self.user_info.get('status', 'Unknown')}")
                print(f"[API] User expiry: {self.user_info.get('exp_date', 'Unknown')}")
                
                return {
                    'success': True,
                    'user_info': self.user_info,
                    'server_info': self.server_info,
                    'message': 'Login successful'
                }
            else:
                print(f"[API] ❌ No user_info in response")
                print(f"[API] Full response: {data}")
                return {
                    'success': False,
                    'message': 'Invalid credentials or server error'
                }
                
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error: {str(e)}"
            print(f"[API] 🔴 ConnectionError: {error_msg}")
            
            # Check for specific connection reset error
            if "10054" in str(e) or "Connection aborted" in str(e):
                print(f"[API] 🔴 Detected connection reset (Error 10054)")
                print(f"[API] This usually indicates:")
                print(f"[API] 1. Server-side rate limiting")
                print(f"[API] 2. Server forcibly closing connections")
                print(f"[API] 3. Firewall/proxy interference")
                print(f"[API] 4. Server overload")
                return {
                    'success': False,
                    'message': 'Server closed connection (rate limiting?). Wait 10 minutes and try again.'
                }
            
            return {
                'success': False,
                'message': error_msg
            }
            
        except requests.exceptions.Timeout as e:
            error_msg = f"Request timeout: {str(e)}"
            print(f"[API] ⏰ Timeout: {error_msg}")
            return {
                'success': False,
                'message': error_msg
            }
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP error {e.response.status_code}: {str(e)}"
            print(f"[API] 🔴 HTTPError: {error_msg}")
            print(f"[API] Response content: {e.response.text[:200] if e.response else 'No response'}")
            return {
                'success': False,
                'message': error_msg
            }
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Request error: {str(e)}"
            print(f"[API] 🔴 RequestException: {error_msg}")
            return {
                'success': False,
                'message': error_msg
            }
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"[API] 💥 Unexpected error: {error_msg}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': error_msg
            }
    
    def _make_api_request(self, action: str, extra_params: Dict = None) -> List[Dict]:
        """Make a standard API request with consistent error handling"""
        if not self.is_authenticated():
            return []
        
        try:
            url = f"{self.base_url}/player_api.php"
            params = {
                'username': self.username,
                'password': self.password,
                'action': action
            }
            
            if extra_params:
                params.update(extra_params)
            
            response = self.session.get(
                url, 
                params=params, 
                timeout=(10, 30)
            )
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            print(f"[API] Error in {action}: {e}")
            return []
    
    def get_live_categories(self) -> List[Dict]:
        """Get live TV categories"""
        return self._make_api_request('get_live_categories')
    
    def get_live_streams(self, category_id: Optional[str] = None) -> List[Dict]:
        """Get live TV streams"""
        extra_params = {'category_id': category_id} if category_id else None
        return self._make_api_request('get_live_streams', extra_params)
    
    def get_short_epg(self, stream_id: str) -> Dict:
        """Get EPG (Electronic Program Guide) for a live stream"""
        if not self.is_authenticated():
            return {}
        
        try:
            url = f"{self.base_url}/player_api.php"
            params = {
                'username': self.username,
                'password': self.password,
                'action': 'get_short_epg',
                'stream_id': stream_id
            }
            
            response = self.session.get(url, params=params, timeout=(10, 30))
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[API] Error getting EPG for stream {stream_id}: {e}")
            return {}
    
    def get_simple_data_table(self, stream_id: str) -> List[Dict]:
        """Get simple EPG data table for a stream"""
        if not self.is_authenticated():
            return []
        
        try:
            url = f"{self.base_url}/player_api.php"
            params = {
                'username': self.username,
                'password': self.password,
                'action': 'get_simple_data_table',
                'stream_id': stream_id
            }
            
            response = self.session.get(url, params=params, timeout=(10, 30))
            response.raise_for_status()
            data = response.json()
            
            # Handle different response formats
            if isinstance(data, dict):
                return data.get('epg_listings', [])
            elif isinstance(data, list):
                return data
            return []
        except Exception as e:
            print(f"[API] Error getting EPG table for stream {stream_id}: {e}")
            return []
    
    def get_vod_categories(self) -> List[Dict]:
        """Get VOD (Movies) categories"""
        return self._make_api_request('get_vod_categories')
    
    def get_vod_streams(self, category_id: Optional[str] = None) -> List[Dict]:
        """Get VOD (Movies) streams"""
        extra_params = {'category_id': category_id} if category_id else None
        return self._make_api_request('get_vod_streams', extra_params)
    
    def get_vod_info(self, vod_id: str) -> Dict:
        """Get detailed VOD (Movie) information including plot"""
        if not self.is_authenticated():
            return {}
        
        try:
            url = f"{self.base_url}/player_api.php"
            params = {
                'username': self.username,
                'password': self.password,
                'action': 'get_vod_info',
                'vod_id': vod_id
            }
            
            response = self.session.get(url, params=params, timeout=(10, 30))
            response.raise_for_status()
            data = response.json()
            
            print(f"[API] VOD Info for {vod_id}: {data.keys() if isinstance(data, dict) else 'Not a dict'}")
            return data
        except Exception as e:
            print(f"[API] Error getting VOD info for {vod_id}: {e}")
            return {}
    
    def get_series_categories(self) -> List[Dict]:
        """Get Series categories"""
        return self._make_api_request('get_series_categories')
    
    def get_series(self, category_id: Optional[str] = None) -> List[Dict]:
        """Get Series"""
        extra_params = {'category_id': category_id} if category_id else None
        return self._make_api_request('get_series', extra_params)
    
    def get_series_info(self, series_id: str) -> Dict:
        """Get detailed series information including plot"""
        if not self.is_authenticated():
            return {}
        
        try:
            url = f"{self.base_url}/player_api.php"
            params = {
                'username': self.username,
                'password': self.password,
                'action': 'get_series_info',
                'series_id': series_id
            }
            
            response = self.session.get(url, params=params, timeout=(10, 30))
            response.raise_for_status()
            data = response.json()
            
            print(f"[API] Series Info for {series_id}: {data.keys() if isinstance(data, dict) else 'Not a dict'}")
            return data
        except Exception as e:
            print(f"[API] Error getting series info for {series_id}: {e}")
            return {}
    
    def get_stream_url(self, stream_id: str, stream_type: str = 'live', extension: str = None, stream_data: Dict = None) -> str:
        """Get stream URL for playback"""
        if not self.is_authenticated():
            return ""
        
        # Ensure we have the correct base URL format
        base_url = self.base_url
        
        # Make sure c0vchump.com uses port 80
        if 'c0vchump.com' in base_url and ':80' not in base_url:
            # Parse and add port if needed
            if base_url.startswith('http://'):
                base_url = base_url.replace('http://c0vchump.com', 'http://c0vchump.com:80')
        
        # Build the URL based on type
        if stream_type == 'live':
            # Live streams typically use .m3u8 or .ts
            ext = extension or 'm3u8'
            url = f"{base_url}/live/{self.username}/{self.password}/{stream_id}.{ext}"
            
        elif stream_type == 'movie':
            # Determine extension from stream data if available
            if stream_data and isinstance(stream_data, dict):
                # Check for container_extension in the stream data
                ext = stream_data.get('container_extension', 
                      stream_data.get('extension', 
                      stream_data.get('video_codec', 'mp4')))
            else:
                ext = extension or 'mp4'
            
            # Handle special cases for extension
            if ext in ['mkv', 'avi', 'mp4', 'mov', 'flv']:
                # These are valid extensions
                pass
            else:
                # Default to mp4 if unknown
                ext = 'mp4'
            
            # Use /movie endpoint for c0vchump.com
            url = f"{base_url}/movie/{self.username}/{self.password}/{stream_id}.{ext}"
            
        elif stream_type == 'series':
            ext = extension or 'mp4'
            url = f"{base_url}/series/{self.username}/{self.password}/{stream_id}.{ext}"
            
        else:
            url = ""
        
        print(f"[API] Generated stream URL: {url}")
        return url
    
    # Keep the old method name for backward compatibility
    def get_movie_info(self, vod_id: str) -> Dict:
        """Alias for get_vod_info for backward compatibility"""
        return self.get_vod_info(vod_id)
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated"""
        return self.user_info is not None
    
    def logout(self):
        """Clear authentication data"""
        self.base_url = None
        self.username = None
        self.password = None
        self.user_info = None
        self.server_info = None
        if self.session:
            self.session.close()
        self.session = self._create_session()