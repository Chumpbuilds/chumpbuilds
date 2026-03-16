"""
Switch User Dialog - Separate from main login
Allows switching profiles without affecting the main login dialog
Current Date and Time (UTC): 2025-01-10 14:46:27
Current User: covchump
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QLineEdit, QPushButton, QComboBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings, QTimer
from PyQt6.QtGui import QCloseEvent
import json
from auth.xtreme_codes import XtremeCodesAPI


class LoginThread(QThread):
    finished = pyqtSignal(dict)
    
    def __init__(self, api, url, username, password):
        super().__init__()
        self.api = api
        self.url = url
        self.username = username
        self.password = password
    
    def run(self):
        result = self.api.login(self.url, self.username, self.password)
        self.finished.emit(result)


class SwitchUserDialog(QDialog):
    """Dedicated dialog for switching user profiles"""
    
    def __init__(self, parent=None, cloud_profiles=None):
        super().__init__(parent)
        self.api = XtremeCodesAPI()
        self.settings = QSettings('IPTVPlayer', 'LoginSettings')
        self.cloud_profiles = cloud_profiles if cloud_profiles is not None else []
        self.current_profile = None
        self.current_url = None
        self.switched_successfully = False
        self.init_ui()
    
    def closeEvent(self, event: QCloseEvent):
        """Handle window close event (X button) - just close dialog"""
        print("[Switch User] Dialog closed - returning to main window")
        event.accept()
    
    def init_ui(self):
        self.setWindowTitle("IPTV Player - Switch Profile")
        self.setFixedSize(440, 480)
        
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        
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
        
        title = QLabel("📺 Switch Profile")
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
            
            self._on_profile_index_changed(0)
        
        if num_profiles > 0:
            username_label = QLabel("Username:")
            username_label.setStyleSheet("color: #b0b0b0; font-size: 12px; margin-top: 5px;")
            layout.addWidget(username_label)
            
            self.username_input = QLineEdit()
            self.username_input.setPlaceholderText("Enter your username")
            self.username_input.setFixedHeight(32)
            self.username_input.setStyleSheet(input_style)
            layout.addWidget(self.username_input)
            
            layout.addSpacing(5)
            
            password_label = QLabel("Password:")
            password_label.setStyleSheet("color: #b0b0b0; font-size: 12px; margin-top: 5px;")
            layout.addWidget(password_label)
            
            self.password_input = QLineEdit()
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.password_input.setPlaceholderText("Enter your password")
            self.password_input.setFixedHeight(32)
            self.password_input.setStyleSheet(input_style)
            self.password_input.returnPressed.connect(self.handle_switch)
            layout.addWidget(self.password_input)
            
            layout.addSpacing(10)
            
            self._load_credentials_for_profile(self.current_profile or '')
        
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
        
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.setContentsMargins(0, 10, 0, 0)
        
        self.switch_button = QPushButton("Switch Profile")
        self.switch_button.setFixedHeight(35)
        self.switch_button.setStyleSheet("""
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
        self.switch_button.clicked.connect(self.handle_switch)
        if num_profiles == 0:
            self.switch_button.setEnabled(False)
        
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
        button_layout.addWidget(self.switch_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
    
    def _on_profile_index_changed(self, index):
        """Update internal URL when user selects a different profile from the dropdown."""
        if 0 <= index < len(self.cloud_profiles):
            profile = self.cloud_profiles[index]
            self.current_url = profile.get('url', '')
            self.current_profile = profile.get('name', '')
            if hasattr(self, 'username_input'):
                self._load_credentials_for_profile(self.current_profile)
    
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
            print(f"[Switch User] Error saving credentials: {e}")
    
    def handle_cancel(self):
        """Handle cancel - just close dialog and return to main window"""
        print("[Switch User] Cancel clicked - returning to main window")
        self.reject()
    
    def handle_switch(self):
        """Handle switching to selected profile"""
        if not self.current_url:
            self.show_error("No server URL available for the selected profile")
            return
        
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        
        if not username or not password:
            self.show_error("Please fill in all required fields")
            return
        
        self.switch_button.setEnabled(False)
        self.show_status("Connecting to server...", "info")
        
        self.login_thread = LoginThread(self.api, self.current_url, username, password)
        self.login_thread.finished.connect(self.on_switch_finished)
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
    
    def on_switch_finished(self, result):
        """Handle switch result"""
        self.switch_button.setEnabled(True)
        
        if result['success']:
            self.show_status("Switch successful!", "success")
            self.switched_successfully = True
            self._save_creds_for_profile(
                self.current_profile or '',
                self.username_input.text(),
                self.password_input.text()
            )
            QTimer.singleShot(500, self.accept)
        else:
            self.show_error(result['message'])
    
    def get_api(self):
        """Return authenticated API if switch was successful"""
        if self.switched_successfully:
            return self.api
        return None
    
    def get_current_profile_name(self):
        """Get current profile name"""
        return self.current_profile or ''
