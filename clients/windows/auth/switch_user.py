"""
Switch User Dialog - Separate from main login
Allows switching profiles without affecting the main login dialog
Current Date and Time (UTC): 2025-01-10 14:46:27
Current User: covchump
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QLineEdit, QPushButton, QCheckBox, QComboBox,
                            QWidget)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings, QTimer
from PyQt6.QtGui import QCloseEvent
import json
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
        result = self.api.login(self.url, self.username, self.password)
        self.finished.emit(result)

class SwitchUserDialog(QDialog):
    """Dedicated dialog for switching user profiles"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.api = XtremeCodesAPI()
        self.settings = QSettings('IPTVPlayer', 'LoginSettings')
        self.profiles = self.load_profiles()
        self.current_profile = None
        self.is_new_profile = False
        self.switched_successfully = False  # Track if user switched successfully
        self.init_ui()
        
        # Set initial state
        if self.profile_combo.count() > 0:
            self.profile_combo.setCurrentIndex(0)
            if self.profile_combo.currentText() == "+ New Profile":
                self.on_profile_changed("+ New Profile")
    
    def closeEvent(self, event: QCloseEvent):
        """Handle window close event (X button) - just close dialog"""
        print("[Switch User] Dialog closed - returning to main window")
        event.accept()
        # Don't do anything else - just close the dialog
    
    def init_ui(self):
        self.setWindowTitle("IPTV Player - Switch Profile")
        self.setFixedSize(440, 620)
        
        # Make it a modal dialog
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        
        # Modern dark theme
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
        """)
        
        # Common input style
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
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(35, 30, 35, 30)
        layout.setSpacing(10)
        
        # Title
        title = QLabel("📺 Switch Profile")
        title.setStyleSheet("""
            font-size: 18px;
            font-weight: 600;
            color: #ffffff;
            margin-bottom: 15px;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Subtitle
        subtitle = QLabel("Select a profile to switch to or create a new one")
        subtitle.setStyleSheet("color: #8b8b8b; font-size: 12px; margin-bottom: 10px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        
        # Profile selector
        profile_label = QLabel("Profile:")
        profile_label.setStyleSheet("color: #b0b0b0; font-size: 12px; margin-top: 5px;")
        layout.addWidget(profile_label)
        
        self.profile_combo = QComboBox()
        self.profile_combo.addItem("+ New Profile")
        for profile_name in sorted(self.profiles.keys()):
            self.profile_combo.addItem(profile_name)
        
        self.profile_combo.setFixedHeight(32)
        self.profile_combo.currentTextChanged.connect(self.on_profile_changed)
        layout.addWidget(self.profile_combo)
        
        layout.addSpacing(5)
        
        # Profile name field (for new profiles)
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
        
        # Hide by default
        self.profile_name_label.hide()
        self.profile_name_input.hide()
        
        layout.addWidget(self.profile_name_container)
        
        # Server URL
        url_label = QLabel("Server URL:")
        url_label.setStyleSheet("color: #b0b0b0; font-size: 12px; margin-top: 5px;")
        layout.addWidget(url_label)
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("http://example.com:8080")
        self.url_input.setFixedHeight(32)
        self.url_input.setStyleSheet(input_style)
        layout.addWidget(self.url_input)
        
        layout.addSpacing(5)
        
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
        self.password_input.returnPressed.connect(self.handle_switch)
        layout.addWidget(self.password_input)
        
        layout.addSpacing(10)
        
        # Remember checkbox
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
        
        # Add stretch
        layout.addStretch()
        
        # Buttons
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
    
    def handle_cancel(self):
        """Handle cancel - just close dialog and return to main window"""
        print("[Switch User] Cancel clicked - returning to main window")
        self.reject()  # This will close the dialog without any other action
    
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
        print(f"[Switch User] Profile changed to: {profile_name}")
        
        if profile_name == "+ New Profile":
            self.setup_new_profile()
        else:
            self.load_profile(profile_name)
    
    def setup_new_profile(self):
        """Setup UI for new profile creation"""
        self.is_new_profile = True
        
        # Show profile name field
        self.profile_name_label.show()
        self.profile_name_input.show()
        self.profile_name_input.clear()
        self.profile_name_input.setFocus()
        
        # Clear all fields
        self.url_input.clear()
        self.username_input.clear()
        self.password_input.clear()
        
        self.remember_checkbox.setChecked(True)
        self.current_profile = None
        self.status_label.hide()
    
    def load_profile(self, profile_name):
        """Load existing profile data"""
        self.is_new_profile = False
        
        # Hide profile name field
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
    
    def handle_switch(self):
        """Handle switching to selected profile"""
        url = self.url_input.text().strip()
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        
        if not all([url, username, password]):
            self.show_error("Please fill in all required fields")
            return
        
        # Check if new profile needs a name
        if self.is_new_profile or self.profile_combo.currentText() == "+ New Profile":
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
        
        self.switch_button.setEnabled(False)
        self.show_status("Connecting to server...", "info")
        
        self.login_thread = LoginThread(self.api, url, username, password)
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
            
            if self.remember_checkbox.isChecked():
                self.save_credentials()
            
            # Close dialog after short delay
            QTimer.singleShot(500, self.accept)
        else:
            self.show_error(result['message'])
    
    def save_credentials(self):
        """Save credentials as profile"""
        if self.is_new_profile or self.profile_combo.currentText() == "+ New Profile":
            profile_name = self.profile_name_input.text().strip()
            if not profile_name:
                profile_name = f"Profile_{len(self.profiles) + 1}"
        else:
            profile_name = self.profile_combo.currentText()
        
        self.profiles[profile_name] = {
            'url': self.url_input.text(),
            'username': self.username_input.text(),
            'password': self.password_input.text()
        }
        
        self.save_profiles()
        self.settings.setValue('last_profile', profile_name)
        self.current_profile = profile_name
        
        # Add new profile to dropdown if needed
        if self.is_new_profile and profile_name not in [
            self.profile_combo.itemText(i) for i in range(self.profile_combo.count())
        ]:
            self.profile_combo.addItem(profile_name)
    
    def get_api(self):
        """Return authenticated API if switch was successful"""
        if self.switched_successfully:
            return self.api
        return None
    
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