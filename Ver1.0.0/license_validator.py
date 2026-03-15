"""
License Validator for IPTV Player
Handles license validation, hardware binding, and user settings sync
Current Date and Time (UTC): 2025-11-16 16:58:57
Current User: covchump
"""

import requests
import hashlib
import platform
import json
import os
import uuid
from typing import Dict, Optional, Any
from PyQt6.QtCore import QSettings, QThread, pyqtSignal
from PyQt6.QtWidgets import QMessageBox, QInputDialog, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit
from PyQt6.QtGui import QFont
import sys

class LicenseDialog(QDialog):
    """Dialog for entering license key"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.license_key = None
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("IPTV Player - License Activation")
        self.setFixedSize(450, 300)
        self.setModal(True)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: white;
            }
            QLabel {
                color: white;
                font-size: 13px;
            }
            QLineEdit {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px;
                color: white;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 2px solid #0d7377;
            }
            QPushButton {
                background-color: #0d7377;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #0e8a8f;
            }
            QPushButton:pressed {
                background-color: #0a5d61;
            }
            QPushButton#cancelButton {
                background-color: transparent;
                color: #b0b0b0;
                border: 1px solid #3d3d3d;
            }
            QPushButton#cancelButton:hover {
                background-color: #2d2d2d;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # Title
        title = QLabel("🔑 License Activation")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #0d7377; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Description
        desc = QLabel("Please enter your license key to activate the IPTV Player:")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #b0b0b0; margin-bottom: 15px;")
        layout.addWidget(desc)
        
        # License key input - NO auto formatter, type exactly as shown
        self.license_input = QLineEdit()
        self.license_input.setPlaceholderText("X87-XXXX-XXXX-XXXX")
        self.license_input.setMaxLength(19)
        layout.addWidget(self.license_input)

        # Format hint
        hint = QLabel("Enter key exactly as provided e.g. X87-RR9X-A3GV-6UZR")
        hint.setStyleSheet("color: #95a5a6; font-size: 11px;")
        layout.addWidget(hint)
        
        # Hardware ID display
        hardware_id = LicenseValidator.get_hardware_id()
        hw_label = QLabel(f"Hardware ID: {hardware_id[:16]}...")
        hw_label.setStyleSheet("color: #95a5a6; font-size: 11px;")
        layout.addWidget(hw_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.activate_button = QPushButton("Activate License")
        self.activate_button.clicked.connect(self.accept_license)
        
        self.cancel_button = QPushButton("Exit Application")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.activate_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
        self.license_input.setFocus()
    
    def accept_license(self):
        """Accept the entered license key - send exactly as typed"""
        license_key = self.license_input.text().strip().upper()
        clean_key = license_key.replace('-', '')
        if len(clean_key) >= 12:
            self.license_key = license_key  # Send exactly as typed WITH dashes
            self.accept()
        else:
            QMessageBox.warning(self, "Invalid License", "Please enter a valid license key (e.g. X87-RR9X-A3GV-6UZR).")

class LicenseValidationThread(QThread):
    """Thread for validating license without blocking UI"""
    validation_complete = pyqtSignal(dict)
    
    def __init__(self, validator, license_key):
        super().__init__()
        self.validator = validator
        self.license_key = license_key
    
    def run(self):
        result = self.validator._validate_with_server(self.license_key)
        self.validation_complete.emit(result)

class LicenseValidator:
    """Handles license validation and user settings management"""
    
    def __init__(self):
        self.license_server = "https://admin.x87player.xyz"
        self.settings = QSettings('IPTVPlayer', 'License')
        self.license_key = None
        self.user_settings = {}
        self.hardware_id = self.get_hardware_id()
        self.is_validated = False
        
        print(f"[License] Initialized with Hardware ID: {self.hardware_id[:16]}...")
        
        stored_license = self.settings.value('license_key', '')
        stored_settings = self.settings.value('user_settings', '{}')
        print(f"[License] Stored license key: {stored_license[:8] + '...' if stored_license else 'None'}")
        print(f"[License] Has stored settings: {len(stored_settings) > 2}")
    
    @staticmethod
    def get_hardware_id() -> str:
        """Generate unique hardware identifier"""
        try:
            machine_id = platform.node()
            processor = platform.processor()
            system = platform.system()
            
            try:
                mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                               for elements in range(0, 2*6, 2)][::-1])
            except:
                mac = "unknown"
            
            combined = f"{machine_id}-{processor}-{system}-{mac}"
            hardware_hash = hashlib.sha256(combined.encode()).hexdigest()
            
            print(f"[License] Hardware ID generated from: {machine_id[:10]}...")
            return hardware_hash
            
        except Exception as e:
            print(f"[License] Error generating hardware ID: {e}")
            fallback = f"{platform.system()}-{platform.node()}"
            return hashlib.md5(fallback.encode()).hexdigest()
    
    def is_license_valid(self) -> bool:
        return self.is_validated and self.license_key is not None
    
    def validate_license(self, show_dialog=True) -> bool:
        """Main license validation method"""
        print("[License] Starting license validation...")
        print(f"[License] Current state - is_validated: {self.is_validated}, license_key: {self.license_key[:8] + '...' if self.license_key else 'None'}")
        
        stored_license = self.settings.value('license_key', '')
        if stored_license:
            print(f"[License] Found stored license: {stored_license[:8]}...")
            validation_result = self._validate_with_server(stored_license)
            
            if validation_result.get('success'):
                self.license_key = stored_license
                self.user_settings = validation_result.get('user_settings', {})
                self.is_validated = True
                
                try:
                    cached_settings = self.settings.value('user_settings', '{}')
                    if cached_settings and cached_settings != '{}':
                        cached_data = json.loads(cached_settings)
                        self.user_settings.update(cached_data)
                except Exception as e:
                    print(f"[License] Error loading cached settings: {e}")
                
                print("[License] ✅ Stored license validated successfully")
                return True
            else:
                print(f"[License] ❌ Stored license invalid: {validation_result.get('message')}")
                self._clear_stored_license()
        else:
            print("[License] No stored license found")
        
        if show_dialog:
            return self._show_license_dialog()
        
        return False
    
    def _clear_stored_license(self):
        self.settings.remove('license_key')
        self.settings.remove('user_settings')
        self.license_key = None
        self.user_settings = {}
        self.is_validated = False
        print("[License] Cleared stored license data")
    
    def _show_license_dialog(self) -> bool:
        dialog = LicenseDialog()
        result = dialog.exec()
        
        if result == QDialog.DialogCode.Accepted and dialog.license_key:
            license_key = dialog.license_key
            print(f"[License] User entered license: {license_key[:8]}...")
            print(f"[License] Full key being sent: {license_key}")  # Debug - remove later
            
            validation_result = self._validate_with_server(license_key)
            
            if validation_result.get('success'):
                self.license_key = license_key
                self.user_settings = validation_result.get('user_settings', {})
                self.is_validated = True
                
                self.settings.setValue('license_key', license_key)
                self.settings.setValue('user_settings', json.dumps(self.user_settings))
                self.settings.sync()
                
                print("[License] ✅ License validation successful")
                QMessageBox.information(None, "License Activated", 
                                       "Your license has been successfully activated!")
                return True
            else:
                error_msg = validation_result.get('message', 'License validation failed')
                print(f"[License] ❌ Validation failed: {error_msg}")
                QMessageBox.critical(None, "License Error", f"License validation failed:\n\n{error_msg}")
                return self._show_license_dialog()
        else:
            print("[License] User cancelled license activation")
            return False
    
    def _validate_with_server(self, license_key: str) -> Dict[str, Any]:
        """Validate license with the server"""
        try:
            print(f"[License] Validating with server: {self.license_server}")
            print(f"[License] Sending key: {license_key}")  # Debug - remove later
            
            validation_data = {
                'license_key': license_key,
                'hardware_id': self.hardware_id,
                'app_version': '1.0.0',
                'platform': platform.system()
            }
            
            response = requests.post(
                f"{self.license_server}/api/license/validate",
                json=validation_data,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            print(f"[License] Server response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"[License] Server response: {data.get('success', False)}")
                print(f"[License] Full server response: {data}")  # Debug - remove later
                return data
            else:
                return {
                    'success': False,
                    'message': f'Server error: HTTP {response.status_code}'
                }
                
        except requests.exceptions.ConnectionError:
            print("[License] Connection error - server unreachable")
            return {
                'success': False,
                'message': 'Cannot connect to license server. Please check your internet connection.'
            }
        except requests.exceptions.Timeout:
            print("[License] Request timeout")
            return {
                'success': False,
                'message': 'License server timeout. Please try again.'
            }
        except Exception as e:
            print(f"[License] Validation error: {e}")
            return {
                'success': False,
                'message': f'Validation error: {str(e)}'
            }
    
    def get_user_settings(self) -> Dict[str, Any]:
        if not self.is_validated:
            return {}
        if self.user_settings:
            return self.user_settings
        try:
            stored_settings = self.settings.value('user_settings', '{}')
            if stored_settings and stored_settings != '{}':
                self.user_settings = json.loads(stored_settings)
                return self.user_settings
        except Exception as e:
            print(f"[License] Error loading stored settings: {e}")
        return {}
    
    def sync_user_settings(self) -> bool:
        if not self.is_validated:
            return False
        try:
            response = requests.post(
                f"{self.license_server}/api/settings/get",
                json={'license_key': self.license_key, 'hardware_id': self.hardware_id},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    self.user_settings = data.get('settings', {})
                    self.settings.setValue('user_settings', json.dumps(self.user_settings))
                    self.settings.sync()
                    print("[License] ✅ User settings synced from server")
                    return True
            return False
        except Exception as e:
            print(f"[License] Settings sync error: {e}")
            return False
    
    def update_user_settings(self, new_settings: Dict[str, Any]) -> bool:
        if not self.is_validated:
            return False
        try:
            response = requests.post(
                f"{self.license_server}/api/settings/update",
                json={
                    'license_key': self.license_key,
                    'hardware_id': self.hardware_id,
                    'settings': new_settings
                },
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    self.user_settings.update(new_settings)
                    self.settings.setValue('user_settings', json.dumps(self.user_settings))
                    self.settings.sync()
                    print("[License] ✅ User settings updated on server")
                    return True
            return False
        except Exception as e:
            print(f"[License] Settings update error: {e}")
            return False
    
    def get_app_customizations(self) -> Dict[str, Any]:
        settings = self.get_user_settings()
        customizations = {
            'theme': settings.get('theme', 'dark'),
            'app_name': settings.get('app_name', 'X87 Player'),
            'primary_color': settings.get('primary_color', '#0d7377'),
            'accent_color': settings.get('accent_color', '#64b5f6'),
            'logo_url': settings.get('logo_url', ''),
            'background_image': settings.get('background_image', ''),
            'enabled_features': settings.get('enabled_features', {
                'live_tv': True,
                'movies': True,
                'search': True,
                'epg': True,
                'series': True,
                'favorites': True
            })
        }
        print(f"[License] Generated customizations for app: {customizations['app_name']}")
        return customizations
    
    def revoke_license(self):
        self._clear_stored_license()
        print("[License] License revoked/cleared")
    
    def get_license_info(self) -> Dict[str, str]:
        if not self.is_validated:
            return {
                'status': 'Not Activated',
                'license_key': 'None',
                'hardware_id': self.hardware_id[:16] + '...'
            }
        return {
            'status': 'Active',
            'license_key': self.license_key[:8] + '...' if self.license_key else 'None',
            'hardware_id': self.hardware_id[:16] + '...'
        }
    
    def force_revalidate(self) -> bool:
        if not self.license_key:
            return False
        print(f"[License] Force revalidating license: {self.license_key[:8]}...")
        validation_result = self._validate_with_server(self.license_key)
        if validation_result.get('success'):
            self.user_settings = validation_result.get('user_settings', {})
            self.is_validated = True
            print("[License] ✅ Force revalidation successful")
            return True
        else:
            print(f"[License] ❌ Force revalidation failed: {validation_result.get('message')}")
            self._clear_stored_license()
            return False

# Singleton instance
_license_validator = None

def get_license_validator() -> LicenseValidator:
    global _license_validator
    if _license_validator is None:
        _license_validator = LicenseValidator()
    return _license_validator

def validate_app_license() -> bool:
    validator = get_license_validator()
    return validator.validate_license()