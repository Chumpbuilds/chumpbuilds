"""
License Validator for IPTV Player (Client-Side Only)
Handles license validation, hardware binding, and version checking
FIXED: Added support for Cloud Profiles (Multi-DNS) from server
FIXED: Added App Branding Support
"""

import requests
import hashlib
import platform
import json
import os
import uuid
import time
import logging
import webbrowser
import sys
from typing import Dict, Optional, Any
from PyQt6.QtCore import QSettings, QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import (QMessageBox, QInputDialog, QDialog, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QLineEdit, QTextEdit)
from PyQt6.QtGui import QFont
from PyQt6 import QtWidgets
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import warnings
from urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings for self-signed certificates
warnings.filterwarnings('ignore', category=InsecureRequestWarning)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [License] - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LicenseValidator:
    """Handles license validation and user settings management"""
    
    # DEFINE CURRENT APP VERSION HERE
    CURRENT_APP_VERSION = "1.0.0"
    
    def __init__(self):
        self.primary_server = "https://admin.x87player.xyz"
        self.endpoints = {
            'health': '/api/health',
            'validate': '/api/license/validate',
        }
        
        self.settings = QSettings('IPTVPlayer', 'License')
        self.branding_settings = QSettings('IPTVPlayer', 'Branding') # Separate settings for branding
        self.license_key = None
        self.license_key_formatted = None
        self.user_settings = {}
        self.cloud_profiles = []  # Store cloud profiles from server
        self.hardware_id = self.get_hardware_id()
        self.is_validated = False
        self.device_bound_error = False
        
        self.session = self._create_session()
        logger.info(f"Initialized with Hardware ID: {self.hardware_id}")
        logger.info(f"Current App Version: {self.CURRENT_APP_VERSION}")
    
    def _create_session(self):
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update({'User-Agent': f'IPTV-Player/{self.CURRENT_APP_VERSION}'})
        return session
    
    @staticmethod
    def get_hardware_id() -> str:
        try:
            machine_id = platform.node()
            processor = platform.processor()
            system = platform.system()
            combined = f"{machine_id}-{processor}-{system}"
            return hashlib.sha256(combined.encode()).hexdigest()
        except Exception as e:
            return hashlib.md5(str(time.time()).encode()).hexdigest()
    
    def is_license_valid(self) -> bool:
        """Quick check if current license is valid - REQUIRED BY UI"""
        return self.is_validated and self.license_key is not None

    def validate_license(self, show_dialog=True) -> bool:
        """Main license validation method"""
        logger.info("Starting license validation...")
        
        stored_license = self.settings.value('license_key', '')
        stored_license_formatted = self.settings.value('license_key_formatted', '')
        
        if stored_license:
            validation_result = self._validate_with_server(stored_license, stored_license_formatted)
            
            if validation_result.get('success'):
                self.license_key = stored_license
                self.license_key_formatted = stored_license_formatted
                self.user_settings = validation_result.get('user_settings', {})
                self.is_validated = True
                
                # --- CACHE BRANDING DATA IMMEDIATELY ---
                # This ensures next time the app opens, the Splash screen has the correct name
                customizations = self.get_app_customizations()
                if customizations.get('app_name'):
                    self.branding_settings.setValue('app_name', customizations['app_name'])
                # ---------------------------------------
                
                return True
            else:
                # Only clear if it's strictly invalid, not if network error
                if "network" not in str(validation_result.get('message')).lower():
                    self.settings.remove('license_key')
                
                if "bound to another device" in str(validation_result.get('message', '')).lower():
                    self.device_bound_error = True

        if show_dialog:
            return self._show_license_dialog()
        return False
    
    def _show_license_dialog(self) -> bool:
        from PyQt6.QtWidgets import QInputDialog # Lazy import
        
        # Simple Input Dialog for Key (Replace with custom dialog class if you have one)
        key, ok = QInputDialog.getText(None, "Activate License", 
                                     "Enter your License Key (X87-XXXX...):")
        
        if ok and key:
            validation_result = self._validate_with_server(key, key)
            
            if validation_result.get('success'):
                self.license_key = key
                self.settings.setValue('license_key', key)
                self.user_settings = validation_result.get('user_settings', {})
                self.is_validated = True
                
                # Cache branding on first activation too
                customizations = self.get_app_customizations()
                if customizations.get('app_name'):
                    self.branding_settings.setValue('app_name', customizations['app_name'])
                
                QMessageBox.information(None, "Success", "License Activated Successfully!")
                return True
            else:
                QMessageBox.critical(None, "Error", f"Validation Failed: {validation_result.get('message')}")
                return self._show_license_dialog() # Retry
        return False

    def _validate_with_server(self, license_key: str, license_key_formatted: str = None, force_refresh: bool = False) -> Dict[str, Any]:
        url = f"{self.primary_server}{self.endpoints['validate']}"
        
        validation_data = {
            'license_key': license_key,
            'hardware_id': self.hardware_id,
            'app_version': self.CURRENT_APP_VERSION,  # Send current version
            'platform': platform.system(),
            'force_refresh': force_refresh
        }
        
        try:
            response = self.session.post(url, json=validation_data, timeout=10, verify=False)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('success'):
                    # --- CAPTURE CLOUD PROFILES ---
                    self.cloud_profiles = data.get('cloud_profiles', [])
                    logger.info(f"Loaded {len(self.cloud_profiles)} cloud profiles")
                    # ------------------------------

                    # --- UPDATE CHECK LOGIC ---
                    server_version = data.get('latest_version', '1.0.0')
                    update_url = data.get('update_url', '')
                    
                    if self._is_version_older(self.CURRENT_APP_VERSION, server_version):
                        logger.info(f"Update available: v{server_version}")
                        self._prompt_update(server_version, update_url)
                    # --------------------------
                    
                    return {
                        'success': True,
                        'user_settings': data.get('user_settings', {})
                    }
                else:
                    return {'success': False, 'message': data.get('message')}
            else:
                 return {'success': False, 'message': f'Server returned {response.status_code}'}
                 
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return {'success': False, 'message': 'Network Error'}

    def _is_version_older(self, current, latest):
        """Compare version strings (e.g., '1.0.0' vs '1.0.1')"""
        try:
            c_parts = [int(x) for x in current.split('.')]
            l_parts = [int(x) for x in latest.split('.')]
            return c_parts < l_parts
        except:
            return False

    def _prompt_update(self, new_version, url):
        """Ask user to update"""
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("Update Available")
        msg.setText(f"A new version (v{new_version}) is available!")
        msg.setInformativeText("It is highly recommended to update for the best experience.\n\nWould you like to download it now?")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)
        
        if msg.exec() == QMessageBox.StandardButton.Yes:
            if url:
                webbrowser.open(url)
                sys.exit(0) # Close app so they can install

    def get_user_settings(self) -> Dict[str, Any]:
        """Get user's customization settings"""
        if not self.is_validated:
            return {}
        return self.user_settings
    
    def get_cloud_profiles(self) -> list:
        """Get list of cloud DNS profiles"""
        return self.cloud_profiles
    
    def get_app_customizations(self) -> Dict[str, Any]:
        """Get app customization settings"""
        settings = self.get_user_settings()
        
        # DEFAULT BRANDING IS SET HERE
        return {
            'theme': settings.get('theme', 'dark'),
            'app_name': settings.get('app_name', 'X87 Player'), # Default to X87 Player
            'primary_color': settings.get('primary_color', '#0d7377'),
            'accent_color': settings.get('accent_color', '#64b5f6'),
            'logo_url': settings.get('logo_url', ''),
            'enabled_features': settings.get('enabled_features', {})
        }
        
    def get_license_info(self) -> Dict[str, Any]:
        """Get basic license info for display"""
        status = "Active" if self.is_validated else "Inactive"
        key = self.license_key or "Not Activated"
        
        # Mask key if active
        if self.is_validated and len(key) > 10:
            key = f"{key[:4]}...{key[-4:]}"
            
        return {
            'status': status,
            'license_key': key,
            'hardware_id': self.hardware_id
        }

# --- REQUIRED SINGLETON HELPERS ---

_license_validator = None

def get_license_validator() -> LicenseValidator:
    """Get or create the license validator instance"""
    global _license_validator
    if _license_validator is None:
        _license_validator = LicenseValidator()
    return _license_validator

def validate_app_license() -> bool:
    """Validate app license - convenience function"""
    validator = get_license_validator()
    return validator.validate_license()