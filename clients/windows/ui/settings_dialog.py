"""
Settings Dialog for IPTV Player
Manages application settings, now with a simplified buffer slider
Current Date and Time (UTC): 2025-11-16 08:05:13
Current User: covchump
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QSpinBox, QGroupBox, QTabWidget,
                            QWidget, QCheckBox, QMessageBox, QSlider,
                            QApplication)
from PyQt6.QtCore import Qt, QSettings, pyqtSignal
from PyQt6.QtGui import QFont

class SettingsDialog(QDialog):
    """Settings dialog for configuring application preferences"""
    
    settings_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings('IPTVPlayer', 'Settings')
        self.vlc_settings = QSettings('IPTVPlayer', 'VLCSettings')
        self.init_ui()
        self.load_settings()
        
    def init_ui(self):
        """Initialize the settings UI"""
        self.setWindowTitle("Settings")
        self.setFixedSize(500, 450)
        self.setModal(True)
        
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; }
            QLabel { color: #ffffff; font-size: 13px; }
            QGroupBox { color: #ffffff; font-size: 14px; font-weight: 600; border: 1px solid #3d3d3d; border-radius: 5px; margin-top: 10px; padding-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
            QPushButton { background-color: #0d7377; color: white; border: none; border-radius: 4px; padding: 8px 20px; font-size: 13px; font-weight: 600; }
            QPushButton:hover { background-color: #0e8a8f; }
            QPushButton#cancelButton { background-color: transparent; color: #b0b0b0; border: 1px solid #3d3d3d; }
            QPushButton#cancelButton:hover { background-color: #2d2d2d; }
            QSlider::groove:horizontal { border: 1px solid #5A5A5A; background: #3d3d3d; height: 8px; border-radius: 4px; }
            QSlider::handle:horizontal { background: #0d7377; border: 1px solid #0d7377; width: 18px; margin: -5px 0; border-radius: 9px; }
            QSlider::sub-page:horizontal { background: #0e8a8f; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title = QLabel("⚙️ Settings")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: white; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # --- MODIFIED: Simplified VLC Buffer Settings ---
        buffer_group = QGroupBox("Stream Buffer")
        buffer_layout = QVBoxLayout()
        
        self.buffer_slider = QSlider(Qt.Orientation.Horizontal)
        self.buffer_slider.setMinimum(1)
        self.buffer_slider.setMaximum(5)
        self.buffer_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.buffer_slider.setTickInterval(1)
        
        slider_labels = QHBoxLayout()
        slider_labels.addWidget(QLabel("Less Delay"))
        slider_labels.addStretch()
        slider_labels.addWidget(QLabel("More Stability"))
        
        self.buffer_value_label = QLabel()
        self.buffer_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.buffer_value_label.setStyleSheet("font-size: 12px; color: #95a5a6;")
        
        self.buffer_slider.valueChanged.connect(self.update_buffer_label)
        
        buffer_layout.addWidget(self.buffer_slider)
        buffer_layout.addLayout(slider_labels)
        buffer_layout.addWidget(self.buffer_value_label)
        
        buffer_group.setLayout(buffer_layout)
        layout.addWidget(buffer_group)

        # --- License Group ---
        license_group = QGroupBox("License")
        license_layout = QVBoxLayout()

        deactivate_button = QPushButton("🔑 Deactivate License")
        deactivate_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(239, 68, 68, 0.2);
                color: #fc8181;
                border: 1px solid #fc8181;
                border-radius: 4px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(239, 68, 68, 0.4);
                color: #ffffff;
            }
        """)
        deactivate_button.clicked.connect(self.deactivate_license)

        license_layout.addWidget(deactivate_button)
        license_group.setLayout(license_layout)
        layout.addWidget(license_group)

        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_settings)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
    def deactivate_license(self):
        """Prompt the user to confirm license deactivation, then wipe ALL data and quit."""
        reply = QMessageBox.warning(
            self,
            "Deactivate License",
            "Are you sure you want to deactivate your license?\n\nThis will permanently delete:\n• Your activation license key\n• All saved IPTV profiles & passwords\n• All app settings\n\nThis is recommended if you are on a shared or public computer.\n\nYou will need your activation code to use the app again.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            # Clear ALL QSettings namespaces - full wipe for public PC safety
            # 1. License key
            license_settings = QSettings('IPTVPlayer', 'License')
            license_settings.clear()
            license_settings.sync()

            # 2. IPTV login profiles & saved passwords
            login_settings = QSettings('IPTVPlayer', 'LoginSettings')
            login_settings.clear()
            login_settings.sync()

            # 3. App settings
            app_settings = QSettings('IPTVPlayer', 'Settings')
            app_settings.clear()
            app_settings.sync()

            # 4. VLC/buffer settings
            vlc_settings = QSettings('IPTVPlayer', 'VLCSettings')
            vlc_settings.clear()
            vlc_settings.sync()

            QMessageBox.information(
                self,
                "License Deactivated",
                "All data has been wiped from this device.\n\nThe application will now close. You will need your activation code to use the app again."
            )
            QApplication.instance().quit()

    def update_buffer_label(self, value):
        """Update the label showing the buffer description"""
        descriptions = {
            1: "Fastest (3 sec buffer) - for perfect connections",
            2: "Fast (7 sec buffer) - good for most connections",
            3: "Balanced (15 sec buffer) - recommended default",
            4: "Stable (25 sec buffer) - for unstable connections",
            5: "Most Stable (40 sec buffer) - for poor connections"
        }
        self.buffer_value_label.setText(descriptions.get(value, ""))

    def load_settings(self):
        """Load saved settings"""
        simple_buffer = self.vlc_settings.value('simple_buffer_level', 3, type=int)
        self.buffer_slider.setValue(simple_buffer)
        self.update_buffer_label(simple_buffer)
    
    def save_settings(self):
        """Save settings and close dialog"""
        slider_value = self.buffer_slider.value()
        
        # --- MODIFIED: Map slider value to large millisecond buffer values ---
        buffer_map = {
            1: (3000, 3000),    # Live, VOD
            2: (7000, 10000),
            3: (15000, 20000),  # Default
            4: (25000, 30000),
            5: (40000, 50000)
        }
        live_buffer, vod_buffer = buffer_map.get(slider_value, (15000, 20000))
        
        # Save to QSettings
        self.vlc_settings.setValue('simple_buffer_level', slider_value)
        self.vlc_settings.setValue('live_caching', live_buffer)
        self.vlc_settings.setValue('file_caching', vod_buffer)
        self.vlc_settings.setValue('network_caching', live_buffer) # Use live buffer for general network
        
        # Apply settings to the player instance
        from player.vlc_player import get_vlc_player
        vlc = get_vlc_player()
        vlc.update_buffer_settings(
            live_caching=live_buffer,
            file_caching=vod_buffer,
            network_caching=live_buffer
        )
        
        self.settings_changed.emit()
        QMessageBox.information(self, "Settings Saved", "Your new buffer settings have been saved.")
        self.accept()