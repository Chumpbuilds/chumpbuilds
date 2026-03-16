"""
Modern Login Dialog - Fixed switch user cancel/close behavior
Added detailed console error logging for connection issues
Current Date and Time (UTC): 2025-11-16 10:05:14
Current User: covchump
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QLineEdit, QPushButton, QComboBox,
                            QApplication)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings, QTimer
from PyQt6.QtGui import QCloseEvent
import json
import sys
import traceback
from auth.xtreme_codes import XtremeCodesAPI

class CustomCheckBox(QCheckBox):
    """Custom checkbox that shows a tick character when checked"""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.updateText(text)
        self.toggled.connect(self.updateDisplay)
        
    def updateDisplay(self, checked):
        """Update the display based on check state"""
        base_text = self.text().replace("☑ ", "").replace("☐ ", "")
        if checked:
            super().setText(f"☑ {base_text}")
        else:
            super().setText(f"☐ {base_text}")
    
    def updateText(self, text):
        """Update the text while preserving check state"""
        base_text = text.replace("☑ ", "").replace("☐ ", "")
        if self.isChecked():
            super().setText(f"☑ {base_text}")
        else:
            super().setText(f"☐ {base_text}")

class LoginThread(QThread):
    finished = pyqtSignal(dict)
    
    def __init__(self, api, url, username, password):
        super().__init__()
        self.api = api
        self.url = url
        self.username = username
        self.password = password
    
    def run(self):
        try:
            print(f"[Login] === DETAILED LOGIN ATTEMPT ===")
            print(f"[Login] Server: {self.url}")
            print(f"[Login] Username: {self.username}")
            print(f"[Login] Password: {'*' * len(self.password)} ({len(self.password)} characters)")
            print(f"[Login] Attempting connection...")
            
            result = self.api.login(self.url, self.username, self.password)
            
            if result['success']:
                print(f"[Login] ✅ SUCCESS: Authentication completed successfully")
                print(f"[Login] User info received: {result.get('user_info', {})}")
            else:
                print(f"[Login] ❌ FAILURE: {result['message']}")
                
        except ConnectionResetError as e:
            error_code = getattr(e, 'errno', 'Unknown')
            print(f"[Login] 🔴 CONNECTION RESET ERROR (Code: {error_code})")
            print(f"[Login] Full error: {str(e)}")
            print(f"[Login] This usually means:")
            print(f"[Login] 1. The IPTV server forcibly closed the connection")
            print(f"[Login] 2. Rate limiting - too many login attempts")
            print(f"[Login] 3. Server is temporarily unavailable")
            print(f"[Login] 4. Firewall/network blocking the connection")
            print(f"[Login] 5. Invalid server URL or port")
            print(f"[Login] Traceback:")
            traceback.print_exc()
            
            result = {
                'success': False, 
                'message': f'Connection reset by server (Error {error_code}). Check console for details.'
            }
            
        except ConnectionError as e:
            print(f"[Login] 🔴 CONNECTION ERROR")
            print(f"[Login] Full error: {str(e)}")
            print(f"[Login] This usually means:")
            print(f"[Login] 1. Server URL is incorrect")
            print(f"[Login] 2. Server is down or unreachable")
            print(f"[Login] 3. Network/internet connection issues")
            print(f"[Login] 4. DNS resolution problems")
            print(f"[Login] Traceback:")
            traceback.print_exc()
            
            result = {
                'success': False, 
                'message': 'Cannot connect to server. Check console for details.'
            }
            
        except TimeoutError as e:
            print(f"[Login] ⏰ TIMEOUT ERROR")
            print(f"[Login] Full error: {str(e)}")
            print(f"[Login] This usually means:")
            print(f"[Login] 1. Server is responding very slowly")
            print(f"[Login] 2. Network congestion")
            print(f"[Login] 3. Server is overloaded")
            print(f"[Login] Traceback:")
            traceback.print_exc()
            
            result = {
                'success': False, 
                'message': 'Connection timeout. Server took too long to respond.'
            }
            
        except Exception as e:
            print(f"[Login] 💥 UNEXPECTED ERROR")
            print(f"[Login] Error type: {type(e).__name__}")
            print(f"[Login] Full error: {str(e)}")
            print(f"[Login] Full traceback:")
            traceback.print_exc()
            
            result = {
                'success': False, 
                'message': f'Unexpected error: {type(e).__name__}. Check console for details.'
            }
        
        print(f"[Login] === END LOGIN ATTEMPT ===")
        self.finished.emit(result)

class ModernLoginDialog(QDialog):
    def __init__(self, parent=None, switch_user=False, cloud_profiles=None):
        super().__init__(parent)
        self.api = XtremeCodesAPI()
        self.settings = QSettings('IPTVPlayer', 'LoginSettings')
        self.switch_user = switch_user
        self.cloud_profiles = cloud_profiles if cloud_profiles is not None else []
        self.current_profile = None
        self.current_url = None
        self.init_ui()
        self._load_last_credentials()
    
    def closeEvent(self, event: QCloseEvent):
        """Handle window close event (X button)"""
        if self.switch_user:
            print("[Login] Switch user dialog closed - returning to main window")
            event.accept()
            return
        else:
            if not self.api.is_authenticated():
                print("[Login] User closed login window - exiting application")
                event.accept()
                if QApplication.instance():
                    QApplication.instance().quit()
                sys.exit(0)
            else:
                event.accept()
    
    def init_ui(self):
        if self.switch_user:
            self.setWindowTitle("IPTV Player - Switch Profile")
        else:
            self.setWindowTitle("IPTV Player - Login")
            
        self.setFixedSize(440, 520)
        
        if self.switch_user:
            self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
            self.setModal(True)
        else:
            self.setWindowFlags(Qt.WindowType.Dialog)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
        """)
        
        input_style = """
            QLineEdit {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 6px 10px;
                color: #ffffff;
                font-size: 13px;
                min-height: 32px;
                max-height: 32px;
            }
            QLineEdit:focus {
                border: 1px solid #0d7377;
            }
        """
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(35, 30, 35, 30)
        layout.setSpacing(10)
        
        title_text = "📺 Switch Profile" if self.switch_user else "📺 IPTV Player Login"
        title = QLabel(title_text)
        title.setStyleSheet("""
            font-size: 18px;
            font-weight: 600;
            color: #ffffff;
            margin-bottom: 15px;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        num_profiles = len(self.cloud_profiles)
        
        if num_profiles == 0:
            # No profiles: show informational message and portal link
            msg_label = QLabel("No DNS profiles have been configured.")
            msg_label.setStyleSheet("color: #b0b0b0; font-size: 13px;")
            msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            msg_label.setWordWrap(True)
            layout.addWidget(msg_label)
            
            info_label = QLabel("Please add DNS (Cloud) profiles in the customer portal to connect.")
            info_label.setStyleSheet("color: #8b8b8b; font-size: 12px;")
            info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            info_label.setWordWrap(True)
            layout.addWidget(info_label)
            
            portal_link = QLabel('<a href="https://portal.x87player.xyz" style="color: #0d7377;">https://portal.x87player.xyz</a>')
            portal_link.setOpenExternalLinks(True)
            portal_link.setAlignment(Qt.AlignmentFlag.AlignCenter)
            portal_link.setStyleSheet("font-size: 13px; margin-top: 5px;")
            layout.addWidget(portal_link)
            
            self.current_url = None
            
        elif num_profiles == 1:
            # Single profile: show label
            profile = self.cloud_profiles[0]
            self.current_url = profile.get('url', '')
            self.current_profile = profile.get('name', '')
            
            profile_label = QLabel("Profile:")
            profile_label.setStyleSheet("color: #b0b0b0; font-size: 12px; margin-top: 5px;")
            layout.addWidget(profile_label)
            
            profile_name_label = QLabel(self.current_profile)
            profile_name_label.setStyleSheet("""
                color: #ffffff;
                font-size: 13px;
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 6px 10px;
                min-height: 32px;
            """)
            layout.addWidget(profile_name_label)
            layout.addSpacing(5)
            
        else:
            # Multiple profiles: show dropdown
            profile_label = QLabel("Profile:")
            profile_label.setStyleSheet("color: #b0b0b0; font-size: 12px; margin-top: 5px;")
            layout.addWidget(profile_label)
            
            self.profile_combo = QComboBox()
            self.profile_combo.setFixedHeight(32)
            for p in self.cloud_profiles:
                self.profile_combo.addItem(p.get('name', ''))
            self.profile_combo.currentIndexChanged.connect(self._on_profile_index_changed)
            layout.addWidget(self.profile_combo)
            layout.addSpacing(5)
            
            # Set initial URL from first profile
            self._on_profile_index_changed(0)
        
        if num_profiles > 0:
            # Username
            username_label = QLabel("Username:")
            username_label.setStyleSheet("color: #b0b0b0; font-size: 12px; margin-top: 5px;")
            layout.addWidget(username_label)
            
            self.username_input = QLineEdit()
            self.username_input.setPlaceholderText("Enter your username")
            self.username_input.setFixedHeight(32)
            self.username_input.setStyleSheet(input_style)
            layout.addWidget(self.username_input)
            
            layout.addSpacing(5)
            
            # Password
            password_label = QLabel("Password:")
            password_label.setStyleSheet("color: #b0b0b0; font-size: 12px; margin-top: 5px;")
            layout.addWidget(password_label)
            
            self.password_input = QLineEdit()
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.password_input.setPlaceholderText("Enter your password")
            self.password_input.setFixedHeight(32)
            self.password_input.setStyleSheet(input_style)
            self.password_input.returnPressed.connect(self.handle_login)
            layout.addWidget(self.password_input)
            
            layout.addSpacing(10)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("""
            QLabel {
                padding: 8px;
                border-radius: 4px;
                font-size: 12px;
                margin-top: 8px;
            }
        """)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.hide()
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.setContentsMargins(0, 10, 0, 0)
        
        self.login_button = QPushButton("Connect")
        self.login_button.setFixedHeight(35)
        self.login_button.setStyleSheet("""
            QPushButton {
                background-color: #0d7377;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 30px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #0e8a8f;
            }
            QPushButton:disabled {
                background-color: #3d3d3d;
                color: #666666;
            }
        """)
        self.login_button.clicked.connect(self.handle_login)
        if num_profiles == 0:
            self.login_button.setEnabled(False)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setFixedHeight(35)
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #b0b0b0;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px 30px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2d2d2d;
            }
        """)
        self.cancel_button.clicked.connect(self.handle_cancel)
        
        button_layout.addStretch()
        button_layout.addWidget(self.login_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        self.center_on_screen()
    
    def center_on_screen(self):
        """Center the dialog on the screen"""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            dialog_geometry = self.frameGeometry()
            center_point = screen_geometry.center()
            dialog_geometry.moveCenter(center_point)
            self.move(dialog_geometry.topLeft())
    
    def _on_profile_index_changed(self, index):
        """Update internal URL when user selects a different profile from the dropdown."""
        if 0 <= index < len(self.cloud_profiles):
            profile = self.cloud_profiles[index]
            self.current_url = profile.get('url', '')
            self.current_profile = profile.get('name', '')
            self._load_credentials_for_profile(self.current_profile)
    
    def _load_last_credentials(self):
        """Load saved username/password for the initially selected profile."""
        if len(self.cloud_profiles) > 0:
            self._load_credentials_for_profile(self.current_profile or '')
    
    def _load_credentials_for_profile(self, profile_name):
        """Load saved credentials for a given profile name from QSettings."""
        if not profile_name or not hasattr(self, 'username_input'):
            return
        saved = self._get_saved_creds(profile_name)
        self.username_input.setText(saved.get('username', ''))
        self.password_input.setText(saved.get('password', ''))
    
    def _get_saved_creds(self, profile_name):
        """Return saved credentials dict for a profile name."""
        try:
            key = f'cloud_creds/{profile_name}'
            raw = self.settings.value(key, '{}')
            return json.loads(raw)
        except Exception:
            return {}
    
    def _save_creds_for_profile(self, profile_name, username, password):
        """Persist credentials for a profile name in QSettings."""
        try:
            key = f'cloud_creds/{profile_name}'
            self.settings.setValue(key, json.dumps({'username': username, 'password': password}))
            self.settings.sync()
        except Exception as e:
            print(f"[Login] Error saving credentials: {e}")
    
    def handle_cancel(self):
        """Handle cancel button click"""
        if self.switch_user:
            print("[Login] Switch user cancelled - returning to main window with current user")
            self.reject()
            return
        else:
            if not self.api.is_authenticated():
                print("[Login] User cancelled login - exiting application")
                if QApplication.instance():
                    QApplication.instance().quit()
                sys.exit(0)
            else:
                self.reject()
    
    def handle_login(self):
        """Handle login process"""
        if not self.current_url:
            self.show_error("No server URL available for the selected profile")
            return
        
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        
        if not username or not password:
            self.show_error("Please fill in all required fields")
            return
        
        self.login_button.setEnabled(False)
        self.show_status("Connecting to server...", "info")
        
        print(f"[Login] 🚀 Starting login attempt...")
        print(f"[Login] Profile: {self.current_profile}")
        
        self.login_thread = LoginThread(self.api, self.current_url, username, password)
        self.login_thread.finished.connect(self.on_login_finished)
        self.login_thread.start()
    
    def show_error(self, message):
        """Show error message"""
        self.status_label.show()
        self.status_label.setText(f"⚠ {message}")
        self.status_label.setStyleSheet("""
            QLabel {
                color: white;
                background-color: #dc3545;
                padding: 8px;
                border-radius: 4px;
                font-size: 12px;
                margin-top: 8px;
            }
        """)
    
    def show_status(self, message, status_type="info"):
        """Show status message"""
        self.status_label.show()
        
        colors = {
            "info": "#17a2b8",
            "success": "#28a745",
            "error": "#dc3545"
        }
        
        color = colors.get(status_type, colors["info"])
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: white;
                background-color: {color};
                padding: 8px;
                border-radius: 4px;
                font-size: 12px;
                margin-top: 8px;
            }}
        """)
    
    def on_login_finished(self, result):
        """Handle login result"""
        self.login_button.setEnabled(True)
        
        if result['success']:
            self.show_status("Login successful!", "success")
            self._save_creds_for_profile(
                self.current_profile or '',
                self.username_input.text(),
                self.password_input.text()
            )
            QTimer.singleShot(500, self.accept)
        else:
            self.show_error(result['message'])
    
    def get_api(self):
        """Return authenticated API"""
        return self.api
    
    def get_current_profile_name(self):
        """Get current profile name"""
        return self.current_profile or ''
    
