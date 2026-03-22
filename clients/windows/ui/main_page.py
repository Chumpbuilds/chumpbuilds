"""
Modern Professional IPTV Player UI - Main Page
Integrated with License Validator and User Customizations
Current Date and Time (UTC): 2025-11-16 16:58:57
Current User: covchump
"""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QPushButton, QLabel, QFrame, QMessageBox, QStackedWidget,
                            QApplication, QGraphicsDropShadowEffect, QMenuBar, QMenu,
                            QLineEdit)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QThread, QTimer, QDateTime, QSettings
from PyQt6.QtGui import QFont, QColor, QAction, QPixmap, QPainter
from auth.modern_login import ModernLoginDialog
from auth.switch_user import SwitchUserDialog
from auth.xtreme_codes import XtremeCodesAPI
from ui.live_tv.live_tv_view import LiveTVView
from ui.movies.movies_view import MoviesView
from ui.series.series_view import SeriesView
from ui.global_search import ModernGlobalSearch
from ui.settings_dialog import SettingsDialog
from ui.favorites.favorites_view import FavoritesView
from ui.favorites.favorites_manager import get_favorites_manager
from player.vlc_player import get_vlc_player
from epg import EPGCache
from license_validator import get_license_validator
import os
import sys

# --- Background thread for VLC pre-warming ---
class VLCPrewarmThread(QThread):
    """A simple thread to run VLC pre-warming in the background."""
    def run(self):
        player = get_vlc_player()
        if player:
            player.prewarm_vlc()

class LicenseInfoDialog(QMessageBox):
    """Dialog showing license information"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.license_validator = get_license_validator()
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("License Information")
        self.setIcon(QMessageBox.Icon.Information)
        
        license_info = self.license_validator.get_license_info()
        customizations = self.license_validator.get_app_customizations()
        
        info_text = f"""
<h3>📜 License Information</h3>
<table style="border-spacing: 10px;">
<tr><td><b>Status:</b></td><td>{license_info['status']}</td></tr>
<tr><td><b>License Key:</b></td><td>{license_info['license_key']}</td></tr>
<tr><td><b>Hardware ID:</b></td><td>{license_info['hardware_id']}</td></tr>
</table>

<h3>🎨 Current Customizations</h3>
<table style="border-spacing: 10px;">
<tr><td><b>App Name:</b></td><td>{customizations.get('app_name', 'Stream Hub')}</td></tr>
<tr><td><b>Theme:</b></td><td>{customizations.get('theme', 'Dark').title()}</td></tr>
<tr><td><b>Primary Color:</b></td><td>{customizations.get('primary_color', '#0d7377')}</td></tr>
</table>

<h3>🔧 Enabled Features</h3>
"""
        
        features = customizations.get('enabled_features', {})
        for feature, enabled in features.items():
            status = "✅" if enabled else "❌"
            info_text += f"<div>{status} {feature.title()}</div>"
        
        self.setText(info_text)
        self.setStandardButtons(QMessageBox.StandardButton.Ok)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.api = None
        self.current_profile = None
        self.current_user = None
        self.global_search = None
        self.live_tv_view = None
        self.movies_view = None
        self.series_view = None
        self.favorites_view = None
        self.vlc_prewarm_thread = None
        self.settings = QSettings('IPTVPlayer', 'Settings')
        
        # License validator and customizations
        self.license_validator = get_license_validator()
        self.customizations = self.license_validator.get_app_customizations()
        
        self.favorites_manager = get_favorites_manager()
        
        cache_dir = os.path.join(os.path.expanduser('~'), '.iptv_cache')
        self.epg_cache = EPGCache(ttl_hours=24, cache_dir=cache_dir)
        print(f"[Main] EPG cache initialized at: {cache_dir}")
        
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_clock_and_status)
        self.update_timer.start(1000)  # Update every second
        
        # Initialize UI but don't show the window yet
        self.init_ui()
        
        # Show login dialog first - window will only show after successful login
        self.show_initial_login()
    
    def update_clock_and_status(self):
        """Update both clock and license status"""
        self.update_clock()
        self.update_license_status()
    
    def update_license_status(self):
        """Update the license status display"""
        if hasattr(self, 'license_status_label'):
            # Force recheck license status
            is_valid = self.license_validator.is_license_valid()
            
            if is_valid:
                self.license_status_label.setText("🟢 Licensed")
                self.license_status_label.setStyleSheet("color: #4ade80; font-size: 12px; background: transparent;")
            else:
                self.license_status_label.setText("🔴 Unlicensed")
                self.license_status_label.setStyleSheet("color: #ef4444; font-size: 12px; background: transparent;")
    
    def apply_customizations(self, customizations):
        """Apply user customizations to the main window"""
        if not customizations:
            customizations = {}
        
        self.customizations = customizations
        
        # Apply custom app name
        app_name = customizations.get('app_name', 'Stream Hub')
        self.setWindowTitle(f"{app_name} - Premium IPTV Player")
        
        # Update header logo and title
        if hasattr(self, 'header_title'):
            self.header_title.setText(app_name.upper())
        
        # Apply custom colors and theme
        self.apply_custom_theme(customizations)
        
        # Update enabled features
        self.update_feature_availability(customizations.get('enabled_features', {}))
        
        # Force license status update
        self.update_license_status()
        
        print(f"[Main] Applied customizations - App: {app_name}")
        print(f"[Main] Theme: {customizations.get('theme', 'dark')}")
        print(f"[Main] Colors: {customizations.get('primary_color', '#0d7377')}")
    
    def apply_custom_theme(self, customizations):
        """Apply custom theme colors"""
        theme = customizations.get('theme', 'dark')
        primary_color = customizations.get('primary_color', '#0d7377')
        accent_color = customizations.get('accent_color', '#64b5f6')
        
        if theme == 'dark':
            gradient_style = f"""
                QMainWindow {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #0f0f1e,
                        stop:0.5 #1a1a2e,
                        stop:1 #16213e);
                }}
                .modern-card {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 {primary_color},
                        stop:1 {accent_color});
                }}
                .header-button {{
                    background: rgba({self.hex_to_rgb(primary_color)}, 0.2);
                    border: 1px solid {primary_color};
                    color: {primary_color};
                }}
                .header-button:hover {{
                    background: rgba({self.hex_to_rgb(primary_color)}, 0.3);
                }}
            """
            self.setStyleSheet(gradient_style)
        
        # Store colors for use in other components
        self.primary_color = primary_color
        self.accent_color = accent_color
    
    def hex_to_rgb(self, hex_color):
        """Convert hex color to RGB string for CSS"""
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return f"{rgb[0]}, {rgb[1]}, {rgb[2]}"
    
    def update_feature_availability(self, enabled_features):
        """Update which features are available based on license"""
        # This will be used to show/hide menu items or disable features
        self.enabled_features = enabled_features
        print(f"[Main] Updated feature availability: {enabled_features}")
    
    def init_ui(self):
        """Initialize the main UI"""
        app_name = self.customizations.get('app_name', 'Stream Hub')
        self.setWindowTitle(f"{app_name} - Premium IPTV Player")
        
        # Set a reasonable minimum size for when the user unmaximizes
        self.setMinimumSize(1000, 700)
        
        # Apply custom theme
        self.apply_custom_theme(self.customizations)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create header
        self.header = self.create_header()
        main_layout.addWidget(self.header)
        
        # Stacked widget for different views
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet("background: transparent;")
        
        # Create home page
        self.home_page = self.create_home_page()
        self.stacked_widget.addWidget(self.home_page)
        
        main_layout.addWidget(self.stacked_widget)
        
        print("[Main] UI initialized, waiting for authentication before showing window")
    
    def create_menu_bar(self):
        """Create professional menu bar"""
        menubar = self.menuBar()
        
        # File Menu
        file_menu = menubar.addMenu('&File')
        
        switch_profile_action = QAction('&Switch Profile', self)
        switch_profile_action.triggered.connect(self.switch_user)
        file_menu.addAction(switch_profile_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('E&xit', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # View Menu
        view_menu = menubar.addMenu('&View')
        
        home_action = QAction('&Home', self)
        home_action.triggered.connect(self.go_back)
        view_menu.addAction(home_action)
        
        view_menu.addSeparator()
        
        # Add view actions based on enabled features
        enabled_features = self.customizations.get('enabled_features', {})
        
        if enabled_features.get('live_tv', True):
            livetv_action = QAction('&Live TV', self)
            livetv_action.triggered.connect(self.show_live_tv)
            view_menu.addAction(livetv_action)
        
        if enabled_features.get('movies', True):
            movies_action = QAction('&Movies', self)
            movies_action.triggered.connect(self.show_movies)
            view_menu.addAction(movies_action)
        
        if enabled_features.get('series', True):
            series_action = QAction('&Series', self)
            series_action.triggered.connect(self.show_series)
            view_menu.addAction(series_action)
        
        if enabled_features.get('search', True):
            search_action = QAction('S&earch', self)
            search_action.triggered.connect(self.show_search)
            view_menu.addAction(search_action)
        
        if enabled_features.get('favorites', True):
            favorites_action = QAction('&Favorites', self)
            favorites_action.triggered.connect(self.show_favorites)
            view_menu.addAction(favorites_action)
        
        # Tools Menu
        tools_menu = menubar.addMenu('&Tools')
        
        settings_action = QAction('&Settings', self)
        settings_action.triggered.connect(self.show_settings)
        tools_menu.addAction(settings_action)
        
        refresh_action = QAction('&Refresh Data', self)
        refresh_action.triggered.connect(self.refresh_data)
        tools_menu.addAction(refresh_action)
        
        tools_menu.addSeparator()
        
        sync_settings_action = QAction('Sync &User Settings', self)
        sync_settings_action.triggered.connect(self.sync_user_settings)
        tools_menu.addAction(sync_settings_action)
        
        revalidate_action = QAction('&Revalidate License', self)
        revalidate_action.triggered.connect(self.revalidate_license)
        tools_menu.addAction(revalidate_action)
        
        # Help Menu
        help_menu = menubar.addMenu('&Help')
        
        license_info_action = QAction('&License Information', self)
        license_info_action.triggered.connect(self.show_license_info)
        help_menu.addAction(license_info_action)
        
        help_menu.addSeparator()
        
        about_action = QAction('&About', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def revalidate_license(self):
        """Force revalidation of license"""
        if self.license_validator.force_revalidate():
            # Reload customizations
            self.customizations = self.license_validator.get_app_customizations()
            self.apply_customizations(self.customizations)
            QMessageBox.information(self, "License Revalidated", "License has been revalidated successfully!")
        else:
            QMessageBox.warning(self, "Revalidation Failed", "Failed to revalidate license. You may need to re-enter your license key.")
            # Show license dialog again
            if self.license_validator.validate_license(show_dialog=True):
                self.customizations = self.license_validator.get_app_customizations()
                self.apply_customizations(self.customizations)
    
    def show_initial_login(self):
        """Show the initial login dialog before displaying main window"""
        cloud_profiles = self.license_validator.get_cloud_profiles()
        login_dialog = ModernLoginDialog(None, switch_user=False, cloud_profiles=cloud_profiles)
        result = login_dialog.exec()
        
        if result == ModernLoginDialog.DialogCode.Accepted:
            # Authentication successful
            self.api = login_dialog.get_api()
            self.current_profile = login_dialog.get_current_profile_name()
            self.current_user = self.api.user_info.get('username', 'Unknown')
            self.update_user_info()

            # Start VLC pre-warming after successful login
            if not self.vlc_prewarm_thread or not self.vlc_prewarm_thread.isRunning():
                self.vlc_prewarm_thread = VLCPrewarmThread()
                self.vlc_prewarm_thread.start()
            
            # Refresh customizations after login
            self.customizations = self.license_validator.get_app_customizations()
            self.apply_customizations(self.customizations)
            
            # Now show the main window maximized
            print("[Main] Authentication successful, showing main window maximized")
            self.showMaximized()
            
        else:
            # User cancelled login or authentication failed
            print("[Main] Login cancelled or failed - exiting application")
            sys.exit()
    
    def create_header(self):
        """Create the header with user info and clock"""
        header = QFrame()
        header.setFixedHeight(70)
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(20, 20, 30, 0.95),
                    stop:1 rgba(20, 20, 30, 0.85));
                border: none;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(30, 0, 30, 0)
        
        # Logo section
        logo_section = QWidget()
        logo_layout = QHBoxLayout(logo_section)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        
        logo = QLabel("🎬")
        logo.setStyleSheet("font-size: 28px; background: transparent;")
        
        # Use custom app name from license
        app_name = self.customizations.get('app_name', 'STREAM HUB')
        self.header_title = QLabel(app_name.upper())
        self.header_title.setStyleSheet("""
            color: white;
            font-size: 24px;
            font-weight: 700;
            letter-spacing: 2px;
            background: transparent;
        """)
        
        logo_layout.addWidget(logo)
        logo_layout.addWidget(self.header_title)
        
        # Back button
        self.back_button = QPushButton("← Back")
        self.back_button.clicked.connect(self.go_back)
        self.back_button.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 20px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.2);
            }
        """)
        self.back_button.hide()
        
        # Info section (right side)
        info_section = QWidget()
        info_layout = QHBoxLayout(info_section)
        info_layout.setSpacing(20)
        
        # UTC Clock
        self.clock_label = QLabel()
        self.clock_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.7);
            font-size: 13px;
            background: transparent;
        """)
        self.update_clock()
        
        # License status indicator
        self.license_status_label = QLabel()
        self.update_license_status()
        
        # User info
        self.user_label = QLabel()
        self.user_label.setStyleSheet("""
            color: #64b5f6;
            font-size: 13px;
            font-weight: 500;
            background: transparent;
        """)
        
        # Profile info
        self.profile_label = QLabel()
        self.profile_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.7);
            font-size: 13px;
            background: transparent;
        """)
        
        # Get custom colors for buttons
        primary_color = self.customizations.get('primary_color', '#0d7377')
        accent_color = self.customizations.get('accent_color', '#64b5f6')
        
        # Settings button
        settings_button = QPushButton("⚙️ Settings")
        settings_button.clicked.connect(self.show_settings)
        settings_button.setStyleSheet(f"""
            QPushButton {{
                background: rgba(100, 100, 100, 0.2);
                color: #b0b0b0;
                border: 1px solid #b0b0b0;
                padding: 8px 20px;
                border-radius: 20px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: rgba(100, 100, 100, 0.3);
                color: #ffffff;
            }}
        """)
        
        # Switch user button
        switch_button = QPushButton("Switch Profile")
        switch_button.clicked.connect(self.switch_user)
        switch_button.setStyleSheet(f"""
            QPushButton {{
                background: rgba(138, 93, 200, 0.2);
                color: #b794f6;
                border: 1px solid #b794f6;
                padding: 8px 20px;
                border-radius: 20px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: rgba(138, 93, 200, 0.3);
            }}
        """)
        
        # Sync button
        sync_button = QPushButton("🔄 Sync")
        sync_button.clicked.connect(self.sync_user_settings)
        sync_button.setStyleSheet(f"""
            QPushButton {{
                background: rgba(74, 222, 128, 0.2);
                color: #4ade80;
                border: 1px solid #4ade80;
                padding: 8px 20px;
                border-radius: 20px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: rgba(74, 222, 128, 0.3);
            }}
        """)
        
        # Logout button
        logout_button = QPushButton("Logout")
        logout_button.clicked.connect(self.logout)
        logout_button.setStyleSheet("""
            QPushButton {
                background: rgba(239, 68, 68, 0.2);
                color: #fc8181;
                border: 1px solid #fc8181;
                padding: 8px 20px;
                border-radius: 20px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: rgba(239, 68, 68, 0.3);
            }
        """)
        
        info_layout.addWidget(self.clock_label)
        info_layout.addWidget(self.license_status_label)
        info_layout.addWidget(self.user_label)
        info_layout.addWidget(self.profile_label)
        info_layout.addWidget(settings_button)
        info_layout.addWidget(switch_button)
        info_layout.addWidget(sync_button)
        info_layout.addWidget(logout_button)
        
        # Search bar for movies/series (hidden by default)
        self.header_search = QLineEdit()
        self.header_search.setPlaceholderText("🔍 Search...")
        self.header_search.setMinimumWidth(300)
        self.header_search.setMaximumWidth(500)
        self.header_search.setStyleSheet("""
            QLineEdit {
                padding: 8px 14px;
                font-size: 13px;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 20px;
                background-color: #2c3e50;
                color: white;
            }
            QLineEdit:focus {
                border: 1px solid rgba(100, 181, 246, 0.6);
            }
        """)
        self.header_search.textChanged.connect(self.on_header_search_changed)
        self.header_search.hide()

        header_layout.addWidget(self.back_button)
        header_layout.addWidget(logo_section)
        header_layout.addStretch()
        header_layout.addWidget(self.header_search)
        header_layout.addStretch()
        header_layout.addWidget(info_section)
        
        return header
    
    def update_clock(self):
        """Update the UTC clock display"""
        current_time = QDateTime.currentDateTimeUtc()
        self.clock_label.setText(
            f"UTC: {current_time.toString('yyyy-MM-dd HH:mm:ss')}"
        )
    
    def sync_user_settings(self):
        """Sync user settings with server"""
        if self.license_validator.sync_user_settings():
            # Reload customizations
            self.customizations = self.license_validator.get_app_customizations()
            self.apply_customizations(self.customizations)
            QMessageBox.information(self, "Settings Synced", "User settings have been synced from the server.")
        else:
            QMessageBox.warning(self, "Sync Failed", "Failed to sync user settings from the server.")
    
    def show_license_info(self):
        """Show license information dialog"""
        dialog = LicenseInfoDialog(self)
        dialog.exec()
    
    def show_about(self):
        """Show about dialog"""
        app_name = self.customizations.get('app_name', 'Stream Hub')
        about_text = f"""
<h2>{app_name}</h2>
<p><b>Version:</b> 1.0.0</p>
<p><b>Build Date:</b> 2025-11-16</p>
<p><b>Developer:</b> covchump</p>
<br>
<p>Professional IPTV Player with advanced features and customization options.</p>
<p>Licensed software - Unauthorized distribution is prohibited.</p>
        """
        QMessageBox.about(self, f"About {app_name}", about_text)
    
    def show_settings(self):
        """Show settings dialog"""
        dialog = SettingsDialog(self)
        dialog.settings_changed.connect(self.on_settings_changed)
        dialog.exec()
    
    def on_settings_changed(self):
        """Handle settings changes"""
        print("[Main] Settings have been changed")
    
    def update_user_info(self):
        """Update displayed user information"""
        if self.api and self.api.is_authenticated():
            self.user_label.setText(f"User: {self.current_user}")
            self.profile_label.setText(f"Profile: {self.current_profile}")
    
    def switch_user(self):
        """Switch to different user profile using dedicated switch dialog"""
        cloud_profiles = self.license_validator.get_cloud_profiles()
        dialog = SwitchUserDialog(self, cloud_profiles=cloud_profiles)
        
        if dialog.exec() == SwitchUserDialog.DialogCode.Accepted:
            new_api = dialog.get_api()
            profile_name = dialog.get_current_profile_name()
            
            if new_api and new_api.is_authenticated():
                if self.api:
                    self.api.logout()
                self.epg_cache.clear()
                
                self.api = new_api
                self.current_profile = profile_name
                self.current_user = self.api.user_info.get('username', 'Unknown')
                self.update_user_info()
                
                self.live_tv_view = None
                self.movies_view = None
                self.series_view = None
                self.global_search = None
                self.favorites_view = None
                
                while self.stacked_widget.count() > 1:
                    widget = self.stacked_widget.widget(1)
                    self.stacked_widget.removeWidget(widget)
                    widget.deleteLater()
                
                self.stacked_widget.setCurrentIndex(0)
                self.back_button.hide()
                
                QMessageBox.information(self, "Profile Switched", f"Successfully switched to profile: {profile_name}")
    
    def refresh_data(self):
        """Refresh all data"""
        reply = QMessageBox.question(
            self, "Refresh Data", 
            "This will clear and reload all data. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.epg_cache.clear()
            
            if self.live_tv_view: 
                self.live_tv_view.load_data()
            if self.movies_view: 
                self.movies_view.load_data()
            if self.series_view: 
                self.series_view.load_data()
            if self.global_search: 
                self.global_search.load_all_content()
            if self.favorites_view: 
                self.favorites_view.refresh_all()
    
    def logout(self):
        """Logout current user"""
        reply = QMessageBox.question(
            self, 'Logout', 
            'Are you sure you want to logout?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.api:
                self.api.logout()
            self.epg_cache.clear()
            self.show_initial_login()
    
    def _stop_all_playback(self):
        """Stop embedded playback on all views before switching."""
        if self.live_tv_view and hasattr(self.live_tv_view, 'stop_playback'):
            self.live_tv_view.stop_playback()
        if self.movies_view and hasattr(self.movies_view, 'stop_playback'):
            self.movies_view.stop_playback()
        if self.series_view and hasattr(self.series_view, 'stop_playback'):
            self.series_view.stop_playback()

    def go_back(self):
        """Go back to home page"""
        self._stop_all_playback()
        self.stacked_widget.setCurrentIndex(0)
        self.back_button.hide()
        self.header_search.hide()
        self.header_search.clear()

    def on_header_search_changed(self, text):
        """Route header search text to the currently active view"""
        current = self.stacked_widget.currentWidget()
        if self.movies_view and current is self.movies_view:
            self.movies_view.filter_categories(text)
            self.movies_view.filter_movies(text)
        elif self.series_view and current is self.series_view:
            self.series_view.filter_categories(text)
            self.series_view.filter_series(text)
    
    def create_home_page(self):
        """Create the modern home page with stylish cards"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(60, 50, 60, 50)
        layout.setSpacing(40)
        
        # Welcome section with custom app name
        welcome_section = QVBoxLayout()
        app_name = self.customizations.get('app_name', 'Stream Hub')
        welcome = QLabel(f"Welcome to {app_name}")
        welcome.setStyleSheet("""
            color: #ffffff;
            font-size: 38px;
            font-weight: 300;
            letter-spacing: 1px;
            margin-bottom: 5px;
        """)
        
        subtitle = QLabel("Your entertainment, reimagined")
        subtitle.setStyleSheet("""
            color: rgba(255, 255, 255, 0.6);
            font-size: 16px;
            font-weight: 400;
            letter-spacing: 0.5px;
        """)
        
        welcome_section.addWidget(welcome, alignment=Qt.AlignmentFlag.AlignCenter)
        welcome_section.addWidget(subtitle, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addLayout(welcome_section)
        
        # Cards container with better spacing
        cards_container = QWidget()
        cards_container.setMaximumWidth(1200)
        cards_layout = QVBoxLayout(cards_container)
        cards_layout.setSpacing(40)
        
        # Get enabled features from license
        enabled_features = self.customizations.get('enabled_features', {})
        
        # First row - main content (only show enabled features)
        first_row = QHBoxLayout()
        first_row.setSpacing(30)
        
        main_categories = []
        if enabled_features.get('live_tv', True):
            main_categories.append(("Live TV", "📺", self.show_live_tv, "#667eea", "#764ba2"))
        if enabled_features.get('movies', True):
            main_categories.append(("Movies", "🎬", self.show_movies, "#f093fb", "#f5576c"))
        if enabled_features.get('series', True):
            main_categories.append(("Series", "📼", self.show_series, "#4facfe", "#00f2fe"))
        
        for title, icon, callback, color1, color2 in main_categories:
            card = self.create_modern_card(title, icon, callback, color1, color2)
            first_row.addWidget(card)
        
        # Second row - utilities (only show enabled features)
        second_row = QHBoxLayout()
        second_row.setSpacing(30)
        
        utility_categories = []
        if enabled_features.get('search', True):
            utility_categories.append(("Search", "🔍", self.show_search, "#43e97b", "#38f9d7"))
        if enabled_features.get('favorites', True):
            utility_categories.append(("Favorites", "⭐", self.show_favorites, "#fa709a", "#fee140"))
        
        # Add spacing to center the cards
        if utility_categories:
            second_row.addStretch(1)
            for title, icon, callback, color1, color2 in utility_categories:
                card = self.create_modern_card(title, icon, callback, color1, color2)
                second_row.addWidget(card)
            second_row.addStretch(1)
        
        if main_categories:
            cards_layout.addLayout(first_row)
        if utility_categories:
            cards_layout.addLayout(second_row)
        
        # Center the cards container
        cards_wrapper = QHBoxLayout()
        cards_wrapper.addStretch()
        cards_wrapper.addWidget(cards_container)
        cards_wrapper.addStretch()
        
        layout.addLayout(cards_wrapper)
        layout.addStretch()
        
        return page
    
    def create_modern_card(self, title, icon, callback, color1, color2):
        """Create a modern, stylish card with gradients and shadows"""
        card = QPushButton()
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.clicked.connect(callback)
        
        # Larger, more modern size
        card.setFixedSize(280, 200)
        
        # Modern gradient style with glassmorphism effect
        card.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {color1},
                    stop:1 {color2});
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 24px;
                color: white;
                font-weight: 600;
                font-size: 18px;
                text-align: center;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {color1},
                    stop:1 {color2});
                border: 2px solid rgba(255, 255, 255, 0.4);
            }}
        """)
        
        # Add drop shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(10)
        shadow.setColor(QColor(0, 0, 0, 60))
        card.setGraphicsEffect(shadow)
        
        # Card content layout
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 30, 20, 30)
        layout.setSpacing(15)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Icon with modern styling
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("""
            font-size: 48px;
            background: transparent;
            color: rgba(255, 255, 255, 0.9);
        """)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Title with modern typography
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.95);
            font-size: 20px;
            font-weight: 600;
            letter-spacing: 0.5px;
            background: transparent;
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Subtle accent line
        accent_line = QFrame()
        accent_line.setFixedSize(40, 3)
        accent_line.setStyleSheet("""
            background: rgba(255, 255, 255, 0.3);
            border-radius: 2px;
        """)
        
        layout.addWidget(icon_label)
        layout.addWidget(accent_line, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        return card
    
    def show_live_tv(self):
        """Show Live TV view"""
        if not self.api or not self.api.is_authenticated():
            QMessageBox.warning(self, "Error", "Please login first")
            return
        
        self._stop_all_playback()
        if not self.live_tv_view:
            self.live_tv_view = LiveTVView(self.api)
            self.stacked_widget.addWidget(self.live_tv_view)
            self.live_tv_view.load_data()
        
        self.stacked_widget.setCurrentWidget(self.live_tv_view)
        self.back_button.show()
        self.header_search.hide()
        self.header_search.clear()
    
    def show_movies(self):
        """Show Movies view"""
        if not self.api or not self.api.is_authenticated():
            QMessageBox.warning(self, "Error", "Please login first")
            return
        
        self._stop_all_playback()
        if not self.movies_view:
            self.movies_view = MoviesView(self.api)
            self.stacked_widget.addWidget(self.movies_view)
            self.movies_view.load_data()
        
        self.stacked_widget.setCurrentWidget(self.movies_view)
        self.back_button.show()
        self.header_search.blockSignals(True)
        self.header_search.clear()
        self.header_search.blockSignals(False)
        self.header_search.setPlaceholderText("🔍 Search movies & categories...")
        self.header_search.show()
    
    def show_series(self):
        """Show Series view"""
        if not self.api or not self.api.is_authenticated():
            QMessageBox.warning(self, "Error", "Please login first")
            return
        
        self._stop_all_playback()
        if not self.series_view:
            self.series_view = SeriesView(self.api)
            self.stacked_widget.addWidget(self.series_view)
            self.series_view.load_data()
        
        self.stacked_widget.setCurrentWidget(self.series_view)
        self.back_button.show()
        self.header_search.blockSignals(True)
        self.header_search.clear()
        self.header_search.blockSignals(False)
        self.header_search.setPlaceholderText("🔍 Search series & categories...")
        self.header_search.show()
    
    def show_search(self):
        """Show Global Search view"""
        if not self.api or not self.api.is_authenticated():
            QMessageBox.warning(self, "Error", "Please login first")
            return
        
        self._stop_all_playback()
        if not self.global_search:
            self.global_search = ModernGlobalSearch(self.api)
            self.stacked_widget.addWidget(self.global_search)
            self.global_search.load_all_content()
        
        self.stacked_widget.setCurrentWidget(self.global_search)
        self.back_button.show()
        self.header_search.hide()
        self.header_search.clear()
    
    def show_favorites(self):
        """Show Favorites view"""
        if not self.api or not self.api.is_authenticated():
            QMessageBox.warning(self, "Error", "Please login first")
            return
        
        self._stop_all_playback()
        if not self.favorites_view:
            self.favorites_view = FavoritesView(self.api)
            self.stacked_widget.addWidget(self.favorites_view)
        else:
            self.favorites_view.refresh_all()
        
        self.stacked_widget.setCurrentWidget(self.favorites_view)
        self.back_button.show()
        self.header_search.hide()
        self.header_search.clear()