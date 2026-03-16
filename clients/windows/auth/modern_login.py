"""
Modern Login Dialog - Cloud Profiles based login
Shows only DNS profiles from customer portal
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

class LoginThread(QThread):
    finished = pyqtSignal(dict)
    
    def __init__(self, api, url, username, password):
        super().__init__()...
        
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