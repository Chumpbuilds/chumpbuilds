"""
Modern Login Dialog
- Added Cloud Profiles Support (Multi-DNS)
- Hides URL for Cloud Profiles
- DYNAMIC APP BRANDING: Uses custom App Name in title and header
Current Date and Time (UTC): 2025-11-16 10:05:14
Current User: covchump
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QLineEdit, QPushButton, QCheckBox, QComboBox,
                            QWidget, QSpacerItem, QSizePolicy, QApplication)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings, QTimer
from PyQt6.QtGui import QFont, QCloseEvent
import json
import sys
import traceback
from auth.xtreme_codes import XtremeCodesAPI
from license_validator import get_license_validator

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
    def __init__(self, parent=None, switch_user=False):
        super().__init__(parent)
        self.api = XtremeCodesAPI()
        self.settings = QSettings('IPTVPlayer', 'LoginSettings')
        
        # --- LOAD BRANDING ---
        self.branding = QSettings('IPTVPlayer', 'Branding')
        self.app_name = self.branding.value('app_name', 'X87 Player')
        if not self.app_name:
            self.app_name = 'X87 Player'
        # ---------------------
        
        self.switch_user = switch_user
        
        # Load local profiles
        self.profiles = self.load_profiles()
        
        # Load cloud profiles from validator
        self.cloud_profiles = {}
        validator = get_license_validator()
        if validator.is_license_valid():
            cloud_list = validator.get_cloud_profiles()
            print(f"[Login] Found {len(cloud_list)} cloud profiles")
            for cp in cloud_list:
                # Use prefix to distinguish and make unique
                key = f"☁️ {cp['name']}"
                self.cloud_profiles[key] = {
                    'url': cp['url'],
                    'username': '',
                    'password': '',
                    'is_cloud': True
                }
        
        self.current_profile = None
        self.is_new_profile = False
        self.init_ui()
        
        # Set initial state based on context
        if switch_user:
            if self.profile_combo.count() > 0:
                self.profile_combo.setCurrentIndex(0)
                if self.profile_combo.currentText() == "+ New Profile":
                    self.on_profile_changed("+ New Profile")
        elif self.profiles or self.cloud_profiles:
            self.load_saved_credentials()
        else:
            self.profile_combo.setCurrentIndex(0)
            self.on_profile_changed("+ New Profile")
    
    def closeEvent(self, event: QCloseEvent):
        """Handle window close event (X button)"""
        if self.switch_user:
            # For switch user, just close the dialog and return to main window
            print("[Login] Switch user dialog closed - returning to main window")
            event.accept()
            return
        else:
            # For initial login, exit the application if not authenticated
            if not self.api.is_authenticated():
                print("[Login] User closed login window - exiting application")
                event.accept()
                # Exit the entire application ONLY for initial login
                if QApplication.instance():
                    QApplication.instance().quit()
                sys.exit(0)
            else:
                # If somehow authenticated, just close the dialog
                event.accept()
    
    def init_ui(self):
        # Use consistent title based on mode
        if self.switch_user:
            self.setWindowTitle(f"{self.app_name} - Switch Profile")
        else:
            self.setWindowTitle(f"{self.app_name} - Login")
            
        # SAME size for both login and switch profile
        self.setFixedSize(440, 620)
        
        # Standard window - use WindowCloseButtonHint to ensure X button is shown
        if self.switch_user:
            # For switch user, make it a modal dialog that returns to parent
            self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
            self.setModal(True)
        else:
            self.setWindowFlags(Qt.WindowType.Dialog)
        
        # Modern dark theme
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
        """)
        
        # Common input style - SAME for both modes
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
            QLineEdit:read-only {
                background-color: #252525;
                color: #808080;
                border: 1px solid #303030;
            }
        """
        
        # Main layout - SAME for both modes
        layout = QVBoxLayout(self)
        layout.setContentsMargins(35, 30, 35, 30)
        layout.setSpacing(10)
        
        # Title - only difference is the text
        title_text = "📺 Switch Profile" if self.switch_user else f"📺 {self.app_name} Login"
        title = QLabel(title_text)
        title.setStyleSheet("""
            font-size: 18px;
            font-weight: 600;
            color: #ffffff;
            margin-bottom: 15px;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Profile selector - SAME for both modes
        profile_label = QLabel("Profile:")
        profile_label.setStyleSheet("color: #b0b0b0; font-size: 12px; margin-top: 5px;")
        layout.addWidget(profile_label)
        
        self.profile_combo = QComboBox()
        self.profile_combo.addItem("+ New Profile")
        
        # Add Cloud Profiles first
        for profile_name in sorted(self.cloud_profiles.keys()):
            self.profile_combo.addItem(profile_name)
            
        # Add saved local profiles
        for profile_name in sorted(self.profiles.keys()):
            # Skip generated saved entries for cloud profiles (which start with ☁️) to avoid duplicates
            if not profile_name.startswith("saved_☁️"):
                self.profile_combo.addItem(profile_name)
        
        self.profile_combo.setFixedHeight(32)
        self.profile_combo.currentTextChanged.connect(self.on_profile_changed)
        layout.addWidget(self.profile_combo)
        
        # Add spacing after profile combo
        layout.addSpacing(5)
        
        # RESERVED SPACE for profile name field - SAME for both modes
        self.profile_name_container = QWidget()
        self.profile_name_container.setFixedHeight(70)
        name_layout = QVBoxLayout(self.profile_name_container)
        name_layout.setContentsMargins(0, 5, 0, 10)
        name_layout.setSpacing(5)
        
        self.profile_name_label = QLabel("Profile Name: *")
        self.profile_name_label.setStyleSheet("color: #b0b0b0; font-size: 12px;")
        name_layout.addWidget(self.profile_name_label)
        
        self.profile_name_input = QLineEdit()
        self.profile_name_input.setPlaceholderText("e.g., Home Server, Work IPTV")
        self.profile_name_input.setFixedHeight(32)
        self.profile_name_input.setStyleSheet(input_style)
        name_layout.addWidget(self.profile_name_input)
        
        # Hide contents but keep space reserved
        self.profile_name_label.hide()
        self.profile_name_input.hide()
        
        layout.addWidget(self.profile_name_container)
        
        # Server URL - SAME for both modes
        self.url_label = QLabel("Server URL:")
        self.url_label.setStyleSheet("color: #b0b0b0; font-size: 12px; margin-top: 5px;")
        layout.addWidget(self.url_label)
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("http://example.com:8080")
        self.url_input.setFixedHeight(32)
        self.url_input.setStyleSheet(input_style)
        layout.addWidget(self.url_input)
        
        layout.addSpacing(5)
        
        # Username - SAME for both modes
        username_label = QLabel("Username:")
        username_label.setStyleSheet("color: #b0b0b0; font-size: 12px; margin-top: 5px;")
        layout.addWidget(username_label)
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter your username")
        self.username_input.setFixedHeight(32)
        self.username_input.setStyleSheet(input_style)
        layout.addWidget(self.username_input)
        
        layout.addSpacing(5)
        
        # Password - SAME for both modes
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
        
        # Checkbox - SAME for both modes
        self.remember_checkbox = CustomCheckBox("Remember this profile")
        self.remember_checkbox.setStyleSheet("""
            QCheckBox {
                color: #b0b0b0;
                font-size: 13px;
                font-family: 'Segoe UI', Arial, sans-serif;
                margin-top: 5px;
            }
            QCheckBox::indicator {
                width: 0px;
                height: 0px;
            }
        """)
        self.remember_checkbox.setChecked(True)
        layout.addWidget(self.remember_checkbox)
        
        # Status label - SAME for both modes
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
        
        # Add stretch to push buttons to bottom
        layout.addStretch()
        
        # Buttons - SAME for both modes
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
        
        # Center the dialog on screen after UI is created
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
            print(f"[Login] Dialog centered on screen")
    
    def handle_cancel(self):
        """Handle cancel button click"""
        if self.switch_user:
            # For switch user, just close the dialog and return to main window
            print("[Login] Switch user cancelled - returning to main window with current user")
            self.reject()  # This closes the dialog and returns to main window
            return
        else:
            # For initial login, exit the application ONLY if not authenticated
            if not self.api.is_authenticated():
                print("[Login] User cancelled login - exiting application")
                if QApplication.instance():
                    QApplication.instance().quit()
                sys.exit(0)
            else:
                # If somehow authenticated, just close the dialog
                self.reject()
    
    def load_profiles(self):
        """Load all saved profiles"""
        profiles_json = self.settings.value('profiles', '{}')
        try:
            return json.loads(profiles_json)
        except:
            return {}
    
    def save_profiles(self):
        """Save all profiles to settings"""
        self.settings.setValue('profiles', json.dumps(self.profiles))
    
    def on_profile_changed(self, profile_name):
        """Handle profile selection change"""
        print(f"[Login] Profile changed to: {profile_name}")
        
        if profile_name == "+ New Profile":
            self.setup_new_profile()
        elif profile_name in self.cloud_profiles:
            self.load_cloud_profile(profile_name)
        else:
            self.load_profile(profile_name)
    
    def setup_new_profile(self):
        """Setup UI for new profile creation"""
        print(f"[Login] Setting up new profile")
        self.is_new_profile = True
        
        # Show URL input and label
        self.url_label.show()
        self.url_input.show()
        
        # Ensure inputs are editable
        self.url_input.setReadOnly(False)
        self.url_input.setStyleSheet("""
            QLineEdit {
                background-color: #2d2d2d; border: 1px solid #3d3d3d;
                border-radius: 4px; padding: 6px 10px; color: #ffffff;
            }
            QLineEdit:focus { border: 1px solid #0d7377; }
        """)
        
        # Show the profile name field contents (space is already reserved)
        self.profile_name_label.show()
        self.profile_name_input.show()
        self.profile_name_input.clear()
        self.profile_name_input.setFocus()
        
        # Clear all fields for new profile
        self.url_input.clear()
        self.username_input.clear()
        self.password_input.clear()
        
        self.remember_checkbox.setChecked(True)
        self.current_profile = None
        self.status_label.hide()
    
    def load_cloud_profile(self, profile_name):
        """Load data from cloud profile - HIDES URL INPUT"""
        print(f"[Login] Loading cloud profile: {profile_name}")
        self.is_new_profile = False
        
        # Hide profile name field
        self.profile_name_label.hide()
        self.profile_name_input.hide()
        self.status_label.hide()
        
        data = self.cloud_profiles[profile_name]
        
        # Set URL but HIDE the field and label
        self.url_input.setText(data.get('url', ''))
        self.url_label.hide()
        self.url_input.hide()
        
        # Try to load saved credentials for this cloud profile
        # We use a prefix to store credentials for cloud profiles locally
        saved_key = f"saved_{profile_name}"
        
        if saved_key in self.profiles:
            print(f"[Login] Found saved credentials for cloud profile")
            self.username_input.setText(self.profiles[saved_key].get('username', ''))
            self.password_input.setText(self.profiles[saved_key].get('password', ''))
        else:
            self.username_input.clear()
            self.password_input.clear()
            
        self.remember_checkbox.setChecked(True)
        self.current_profile = profile_name

    def load_profile(self, profile_name):
        """Load existing profile data"""
        print(f"[Login] Loading profile: {profile_name}")
        self.is_new_profile = False
        
        # Show URL input and label for regular profiles
        self.url_label.show()
        self.url_input.show()
        
        # Enable editing for local profiles
        self.url_input.setReadOnly(False)
        self.url_input.setStyleSheet("""
            QLineEdit {
                background-color: #2d2d2d; border: 1px solid #3d3d3d;
                border-radius: 4px; padding: 6px 10px; color: #ffffff;
            }
            QLineEdit:focus { border: 1px solid #0d7377; }
        """)
        
        # Hide the profile name field contents (space stays reserved)
        self.profile_name_label.hide()
        self.profile_name_input.hide()
        self.status_label.hide()
        
        if profile_name in self.profiles:
            profile_data = self.profiles[profile_name]
            self.url_input.setText(profile_data.get('url', ''))
            self.username_input.setText(profile_data.get('username', ''))
            self.password_input.setText(profile_data.get('password', ''))
            self.remember_checkbox.setChecked(True)
            self.current_profile = profile_name
    
    def handle_login(self):
        """Handle login process"""
        url = self.url_input.text().strip()
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        
        if not all([url, username, password]):
            self.show_error("Please fill in all required fields")
            return
        
        # Check if new profile needs a name (only for regular new profiles)
        is_cloud = self.profile_combo.currentText() in self.cloud_profiles
        
        if not is_cloud and (self.is_new_profile or self.profile_combo.currentText() == "+ New Profile"):
            profile_name = self.profile_name_input.text().strip()
            if not profile_name:
                self.show_error("Please enter a profile name")
                self.profile_name_input.setFocus()
                return
            
            if profile_name in self.profiles:
                self.show_error(f"Profile '{profile_name}' already exists")
                self.profile_name_input.selectAll()
                self.profile_name_input.setFocus()
                return
        
        self.login_button.setEnabled(False)
        self.show_status("Connecting to server...", "info")
        
        print(f"[Login] 🚀 Starting login attempt...")
        print(f"[Login] Profile: {self.get_current_profile_name()}")
        
        self.login_thread = LoginThread(self.api, url, username, password)
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
            if self.remember_checkbox.isChecked():
                self.save_credentials()
            QTimer.singleShot(500, self.accept)
        else:
            self.show_error(result['message'])
    
    def save_credentials(self):
        """Save credentials as profile"""
        current_text = self.profile_combo.currentText()
        
        # Handle Cloud Profiles
        if current_text in self.cloud_profiles:
            # Save credential mapping for this cloud profile
            # We prefix with 'saved_' to keep it separate in the profiles dict but link it
            save_key = f"saved_{current_text}"
            print(f"[Login] Saving credentials for cloud profile: {current_text}")
            
            self.profiles[save_key] = {
                'url': self.url_input.text(), # Should match cloud URL
                'username': self.username_input.text(),
                'password': self.password_input.text()
            }
            self.save_profiles()
            self.settings.setValue('last_profile', current_text)
            self.current_profile = current_text
            return

        # Handle Standard Profiles
        if self.is_new_profile or current_text == "+ New Profile":
            profile_name = self.profile_name_input.text().strip()
            if not profile_name:
                profile_name = f"Profile_{len(self.profiles) + 1}"
            print(f"[Login] Saving new profile: {profile_name}")
        else:
            profile_name = current_text
            print(f"[Login] Updating profile: {profile_name}")
        
        self.profiles[profile_name] = {
            'url': self.url_input.text(),
            'username': self.username_input.text(),
            'password': self.password_input.text()
        }
        
        self.save_profiles()
        self.settings.setValue('last_profile', profile_name)
        self.current_profile = profile_name
        
        if self.is_new_profile and profile_name not in [
            self.profile_combo.itemText(i) for i in range(self.profile_combo.count())
        ]:
            self.profile_combo.addItem(profile_name)
            print(f"[Login] Added '{profile_name}' to dropdown")
    
    def load_saved_credentials(self):
        """Load last used profile"""
        last_profile = self.settings.value('last_profile', '')
        if last_profile:
            index = self.profile_combo.findText(last_profile)
            if index >= 0:
                self.profile_combo.setCurrentIndex(index)
                # The on_profile_changed handler will call load_profile/load_cloud_profile
    
    def get_api(self):
        """Return authenticated API"""
        return self.api
    
    def get_current_profile_name(self):
        """Get current profile name"""
        if self.current_profile:
            return self.current_profile
        
        if self.is_new_profile:
            profile_name = self.profile_name_input.text().strip()
            if profile_name:
                return profile_name
            return f"Profile_{len(self.profiles) + 1}"
        
        return self.profile_combo.currentText()