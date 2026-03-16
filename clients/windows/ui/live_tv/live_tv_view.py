"""
Live TV View - 3-column layout with Categories, Channels, and EPG/Artwork
Uses EPG module with 24-hour caching - Fixed text cutoff issue
Added Favorites functionality
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                            QListWidgetItem, QLabel, QPushButton, QLineEdit,
                            QSplitter, QProgressBar, QMessageBox, QFrame, QMenu,
                            QSlider)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl, QPoint
from PyQt6.QtGui import QFont, QPixmap, QColor, QAction, QCursor
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from player.vlc_player import get_vlc_player, get_embedded_vlc_player
from epg import EPGCache, EPGParser
from epg.epg_loader import EPGLoaderThread
from datetime import datetime
import os

# Add favorites import
try:
    from ..favorites.favorites_manager import get_favorites_manager
except ImportError:
    # Fallback if favorites module doesn't exist yet
    def get_favorites_manager():
        return None

class DataLoaderThread(QThread):
    categories_loaded = pyqtSignal(list)
    channels_loaded = pyqtSignal(list)
    all_channels_loaded = pyqtSignal(list)
    
    def __init__(self, api, load_type='categories', category_id=None):
        super().__init__()
        self.api = api
        self.load_type = load_type
        self.category_id = category_id
    
    def run(self):
        if self.load_type == 'categories':
            categories = self.api.get_live_categories()
            self.categories_loaded.emit(categories)
        elif self.load_type == 'all_channels':
            channels = self.api.get_live_streams(None)
            self.all_channels_loaded.emit(channels)
        elif self.load_type == 'channels':
            channels = self.api.get_live_streams(self.category_id)
            self.channels_loaded.emit(channels)

class LiveTVView(QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.current_category = None
        self.current_channel = None
        self.player = get_vlc_player()
        self.all_channels = []
        self.category_channels = []
        self.stored_categories = []
        self.network_manager = QNetworkAccessManager()
        
        # Initialize favorites manager
        self.favorites_manager = get_favorites_manager()
        
        # Initialize EPG cache (24-hour TTL, persisted to cache folder)
        cache_dir = os.path.join(os.path.expanduser('~'), '.iptv_cache')
        self.epg_cache = EPGCache(ttl_hours=24, cache_dir=cache_dir)
        
        print(f"[Live TV] EPG cache initialized at: {cache_dir}")
        
        # Cleanup timer - remove expired entries every hour
        self.cleanup_timer = QTimer()
        self.cleanup_timer.timeout.connect(self.cleanup_epg_cache)
        self.cleanup_timer.start(3600000)  # 1 hour = 3,600,000 ms
        
        # Show cache stats on startup
        self.show_cache_stats()
        
        self.init_ui()
    
    def cleanup_epg_cache(self):
        """Periodic cleanup of expired EPG cache entries"""
        self.epg_cache.cleanup_expired()
        self.show_cache_stats()
    
    def show_cache_stats(self):
        """Display cache statistics"""
        stats = self.epg_cache.get_stats()
        print(f"\n[EPG Cache Stats]")
        print(f"  Total entries: {stats['total_entries']}")
        print(f"  Active entries: {stats['active_entries']}")
        print(f"  Expired entries: {stats['expired_entries']}")
        print(f"  TTL: {stats['ttl_hours']} hours")
        if 'next_expiry' in stats:
            print(f"  Next expiry: {stats['next_expiry']} ({stats['hours_until_next_expiry']:.1f} hours)")
        print()
    
    def init_ui(self):
        # Main horizontal layout
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create three columns
        self.create_categories_column()
        self.create_channels_column()
        self.create_epg_column()
        
        # Add columns to main layout with splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.categories_widget)
        splitter.addWidget(self.channels_widget)
        splitter.addWidget(self.epg_widget)
        
        # Set column widths (right column gets extra space for the embedded player)
        splitter.setSizes([220, 220, 760])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 2)
        
        main_layout.addWidget(splitter)
        self.setLayout(main_layout)
        
        # Apply dark theme
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
            }
            QLabel {
                color: white;
            }
        """)
    
    def create_categories_column(self):
        """Create the categories column (25% width)"""
        self.categories_widget = QWidget()
        self.categories_widget.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                border-right: 1px solid #3a3a3a;
            }
        """)
        
        layout = QVBoxLayout(self.categories_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Title
        title = QLabel("Categories")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #3498db; padding: 5px;")
        layout.addWidget(title)
        
        # Search box for categories
        self.category_search = QLineEdit()
        self.category_search.setPlaceholderText("🔍 Search categories...")
        self.category_search.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                font-size: 12px;
                border: 1px solid #3498db;
                border-radius: 4px;
                background-color: #2c3e50;
                color: white;
            }
            QLineEdit:focus {
                border: 2px solid #2ecc71;
            }
        """)
        self.category_search.textChanged.connect(self.filter_categories)
        layout.addWidget(self.category_search)
        
        # Categories list
        self.categories_list = QListWidget()
        self.categories_list.setStyleSheet("""
            QListWidget {
                background-color: #2c3e50;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #1a1a1a;
            }
            QListWidget::item:selected {
                background-color: #3498db;
            }
            QListWidget::item:hover {
                background-color: #34495e;
            }
        """)
        self.categories_list.itemClicked.connect(self.on_category_selected)
        layout.addWidget(self.categories_list)
        
        # Category count label
        self.category_count = QLabel("0 categories")
        self.category_count.setStyleSheet("color: #95a5a6; font-size: 11px; padding: 5px;")
        layout.addWidget(self.category_count)
    
    def create_channels_column(self):
        """Create the channels column (25% width)"""
        self.channels_widget = QWidget()
        self.channels_widget.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                border-right: 1px solid #3a3a3a;
            }
        """)
        
        layout = QVBoxLayout(self.channels_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Title
        self.channels_title = QLabel("Channels")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        self.channels_title.setFont(title_font)
        self.channels_title.setStyleSheet("color: #e74c3c; padding: 5px;")
        layout.addWidget(self.channels_title)
        
        # Search box for channels
        self.channel_search = QLineEdit()
        self.channel_search.setPlaceholderText("🔍 Search all channels...")
        self.channel_search.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                font-size: 12px;
                border: 1px solid #e74c3c;
                border-radius: 4px;
                background-color: #2c3e50;
                color: white;
            }
            QLineEdit:focus {
                border: 2px solid #2ecc71;
            }
        """)
        self.channel_search.textChanged.connect(self.filter_channels)
        layout.addWidget(self.channel_search)
        
        # Channels list - ADD CONTEXT MENU
        self.channels_list = QListWidget()
        self.channels_list.setStyleSheet("""
            QListWidget {
                background-color: #2c3e50;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #1a1a1a;
            }
            QListWidget::item:selected {
                background-color: #e74c3c;
            }
            QListWidget::item:hover {
                background-color: #34495e;
            }
        """)
        self.channels_list.itemClicked.connect(self.on_channel_selected)
        self.channels_list.itemDoubleClicked.connect(self.play_channel)
        
        # ADD CONTEXT MENU FOR FAVORITES
        self.channels_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.channels_list.customContextMenuRequested.connect(self.show_channel_context_menu)
        
        layout.addWidget(self.channels_list)
        
        # Channel count label
        self.channel_count = QLabel("0 channels")
        self.channel_count.setStyleSheet("color: #95a5a6; font-size: 11px; padding: 5px;")
        layout.addWidget(self.channel_count)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setMaximumHeight(3)
        self.progress_bar.hide()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #2c3e50;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #3498db;
            }
        """)
        layout.addWidget(self.progress_bar)
    
    def show_channel_context_menu(self, position: QPoint):
        """Show context menu for channel with favorites option"""
        item = self.channels_list.itemAt(position)
        if not item:
            return
        
        channel_data = item.data(Qt.ItemDataRole.UserRole)
        if not channel_data:
            return
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2c3e50;
                border: 1px solid #34495e;
                border-radius: 5px;
                padding: 5px;
            }
            QMenu::item {
                padding: 8px 20px;
                color: white;
            }
            QMenu::item:selected {
                background-color: #34495e;
            }
        """)
        
        # Play action
        play_action = QAction("▶ Play Channel", self)
        play_action.triggered.connect(lambda: self.play_channel(item))
        menu.addAction(play_action)
        
        # Favorites actions
        if self.favorites_manager:
            menu.addSeparator()
            
            stream_id = channel_data.get('stream_id')
            is_favorite = self.favorites_manager.is_favorite('channels', stream_id)
            
            if is_favorite:
                remove_fav_action = QAction("❌ Remove from Favorites", self)
                remove_fav_action.triggered.connect(lambda: self.remove_from_favorites(channel_data))
                menu.addAction(remove_fav_action)
            else:
                add_fav_action = QAction("⭐ Add to Favorites", self)
                add_fav_action.triggered.connect(lambda: self.add_to_favorites(channel_data))
                menu.addAction(add_fav_action)
        
        menu.exec(QCursor.pos())
    
    def add_to_favorites(self, channel_data):
        """Add channel to favorites"""
        if self.favorites_manager and self.favorites_manager.add_favorite('channels', channel_data):
            self.status_label.setText(f"✓ Added to favorites: {channel_data.get('name', 'Unknown')}")
            self.status_label.setStyleSheet("color: #2ecc71; padding: 5px;")
            # Update main window favorites count if available
            if self.window() and hasattr(self.window(), 'update_favorites_count'):
                self.window().update_favorites_count()
        else:
            self.status_label.setText("Already in favorites")
            self.status_label.setStyleSheet("color: #f39c12; padding: 5px;")
    
    def remove_from_favorites(self, channel_data):
        """Remove channel from favorites"""
        stream_id = channel_data.get('stream_id')
        if self.favorites_manager and stream_id and self.favorites_manager.remove_favorite('channels', stream_id):
            self.status_label.setText(f"✓ Removed from favorites: {channel_data.get('name', 'Unknown')}")
            self.status_label.setStyleSheet("color: #e74c3c; padding: 5px;")
            # Update main window favorites count if available
            if self.window() and hasattr(self.window(), 'update_favorites_count'):
                self.window().update_favorites_count()
    
    def create_epg_column(self):
        """Create the EPG column with embedded VLC player, controls, channel info, and EPG."""
        self.epg_widget = QWidget()
        self.epg_widget.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
            }
        """)

        layout = QVBoxLayout(self.epg_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # ── 1. Embedded video player frame ────────────────────────────────────
        self.video_frame = QFrame()
        self.video_frame.setStyleSheet("background-color: #000000; border-radius: 6px;")
        self.video_frame.setMinimumHeight(360)
        # Give the video frame a native HWND so VLC can render directly into it
        self.video_frame.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)

        # Placeholder label shown when nothing is playing
        self.video_placeholder = QLabel("📺  Select a channel and click Play to start streaming")
        self.video_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_placeholder.setWordWrap(True)
        self.video_placeholder.setStyleSheet("color: #666666; font-size: 13px; background: transparent;")

        # Use a layout so the placeholder is centered inside the frame
        _vf_layout = QVBoxLayout(self.video_frame)
        _vf_layout.setContentsMargins(10, 10, 10, 10)
        _vf_layout.addStretch()
        _vf_layout.addWidget(self.video_placeholder)
        _vf_layout.addStretch()

        layout.addWidget(self.video_frame, stretch=3)

        # Create the embedded player
        self.embedded_player = get_embedded_vlc_player(self.video_frame)

        # ── 2. Player control bar ─────────────────────────────────────────────
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)

        self.play_embedded_btn = QPushButton("▶ Play")
        self.play_embedded_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 8px 14px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #229954; }
            QPushButton:pressed { background-color: #1e8449; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)
        self.play_embedded_btn.setEnabled(False)
        self.play_embedded_btn.clicked.connect(self.play_channel_embedded)

        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 8px 14px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #c0392b; }
            QPushButton:pressed { background-color: #a93226; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_playback)

        self.fullscreen_btn = QPushButton("⛶ Fullscreen")
        self.fullscreen_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 14px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #2980b9; }
            QPushButton:pressed { background-color: #21618c; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)
        self.fullscreen_btn.setEnabled(False)
        self.fullscreen_btn.clicked.connect(self.embedded_player.go_fullscreen)

        self.open_external_btn = QPushButton("↗ Open in VLC")
        self.open_external_btn.setStyleSheet("""
            QPushButton {
                background-color: #7f8c8d;
                color: white;
                border: none;
                padding: 8px 14px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #6c7a7d; }
            QPushButton:pressed { background-color: #5d6d6e; }
            QPushButton:disabled { background-color: #95a5a6; }
        """)
        self.open_external_btn.setEnabled(False)
        self.open_external_btn.clicked.connect(self.play_channel_external)

        # Volume slider
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #34495e;
                height: 5px;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #3498db;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::sub-page:horizontal {
                background: #3498db;
                border-radius: 2px;
            }
        """)
        self.volume_slider.valueChanged.connect(self.embedded_player.set_volume)

        self.mute_btn = QPushButton("🔊")
        self.mute_btn.setFixedWidth(36)
        self.mute_btn.setStyleSheet("""
            QPushButton {
                background-color: #2c3e50;
                color: white;
                border: none;
                padding: 6px;
                font-size: 14px;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #34495e; }
        """)
        self.mute_btn.clicked.connect(self._on_mute_toggled)

        controls_layout.addWidget(self.play_embedded_btn)
        controls_layout.addWidget(self.stop_btn)
        controls_layout.addWidget(self.fullscreen_btn)
        controls_layout.addWidget(self.open_external_btn)
        controls_layout.addStretch()
        controls_layout.addWidget(self.mute_btn)
        controls_layout.addWidget(self.volume_slider)

        layout.addLayout(controls_layout)

        # ── 3. Channel Info (hidden orphan widgets — referenced by other methods) ──
        # Not added to the layout so the video player fills more space,
        # but kept as attributes so on_channel_selected / on_epg_loaded / etc. don't crash.
        self.channel_logo = QLabel()
        self.channel_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.channel_logo.setFixedSize(80, 80)
        self.channel_logo.setText("📺")
        self.channel_logo.setScaledContents(True)
        logo_font = QFont()
        logo_font.setPointSize(32)
        self.channel_logo.setFont(logo_font)

        self.channel_name = QLabel("No Channel Selected")
        name_font = QFont()
        name_font.setPointSize(14)
        name_font.setBold(True)
        self.channel_name.setFont(name_font)

        self.channel_info_label = QLabel("Select a channel to view program guide")

        # ── 4. EPG Section ────────────────────────────────────────────────────
        epg_header = QHBoxLayout()
        epg_label = QLabel("📅 Program Guide")
        epg_label_font = QFont()
        epg_label_font.setPointSize(14)
        epg_label_font.setBold(True)
        epg_label.setFont(epg_label_font)
        epg_label.setStyleSheet("color: #3498db; padding: 5px;")
        epg_header.addWidget(epg_label)

        # EPG loading/cache indicator
        self.epg_loading = QLabel("")
        self.epg_loading.setStyleSheet("color: #95a5a6; font-size: 11px;")
        epg_header.addWidget(self.epg_loading)
        epg_header.addStretch()

        layout.addLayout(epg_header)

        # EPG List
        self.epg_list = QListWidget()
        self.epg_list.setStyleSheet("""
            QListWidget {
                background-color: #2c3e50;
                border: none;
                border-radius: 8px;
                padding: 5px;
            }
            QListWidget::item {
                background-color: transparent;
                padding: 12px 10px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
                color: white;
            }
            QListWidget::item:hover {
                background-color: rgba(255, 255, 255, 0.05);
            }
            QListWidget::item:selected {
                background-color: rgba(52, 152, 219, 0.3);
            }
        """)
        layout.addWidget(self.epg_list, stretch=2)

        # ── 5. Status label ───────────────────────────────────────────────────
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #2ecc71; padding: 5px;")
        layout.addWidget(self.status_label)
    
    def load_data(self):
        """Load categories and all channels"""
        self.progress_bar.show()
        # Load categories
        self.loader_thread = DataLoaderThread(self.api, 'categories')
        self.loader_thread.categories_loaded.connect(self.on_categories_loaded)
        self.loader_thread.start()
        
        # Load all channels for search
        self.all_loader_thread = DataLoaderThread(self.api, 'all_channels')
        self.all_loader_thread.all_channels_loaded.connect(self.on_all_channels_loaded)
        self.all_loader_thread.start()
    
    def on_all_channels_loaded(self, channels):
        """Store all channels for search functionality"""
        self.all_channels = channels
    
    def on_categories_loaded(self, categories):
        self.progress_bar.hide()
        self.categories_list.clear()
        self.stored_categories = categories
        
        for category in categories:
            item = QListWidgetItem(f"📁 {category.get('category_name', 'Unknown')}")
            item.setData(Qt.ItemDataRole.UserRole, category.get('category_id'))
            self.categories_list.addItem(item)
        
        self.category_count.setText(f"{len(categories)} categories")
        
        # Auto-select first category
        if self.categories_list.count() > 0:
            self.categories_list.setCurrentRow(0)
            self.on_category_selected(self.categories_list.item(0))
    
    def filter_categories(self, text):
        """Filter categories based on search text"""
        self.categories_list.clear()
        search_text = text.lower().strip()
        
        if not self.stored_categories:
            return
        
        matches = 0
        for category in self.stored_categories:
            category_name = category.get('category_name', '').lower()
            if not search_text or search_text in category_name:
                item = QListWidgetItem(f"📁 {category.get('category_name', 'Unknown')}")
                item.setData(Qt.ItemDataRole.UserRole, category.get('category_id'))
                self.categories_list.addItem(item)
                matches += 1
        
        self.category_count.setText(f"{matches} categories")
    
    def on_category_selected(self, item):
        if not item:
            return
        
        category_id = item.data(Qt.ItemDataRole.UserRole)
        category_name = item.text().replace('📁 ', '')
        self.current_category = category_id
        
        # Update channels title
        self.channels_title.setText(f"Channels - {category_name}")
        
        self.progress_bar.show()
        self.loader_thread = DataLoaderThread(self.api, 'channels', category_id)
        self.loader_thread.channels_loaded.connect(self.on_channels_loaded)
        self.loader_thread.start()
    
    def on_channels_loaded(self, channels):
        self.progress_bar.hide()
        self.channels_list.clear()
        self.category_channels = channels
        
        for channel in channels:
            # Add favorite indicator if applicable
            stream_id = channel.get('stream_id')
            is_fav = self.favorites_manager and self.favorites_manager.is_favorite('channels', stream_id)
            prefix = "⭐ " if is_fav else "📺 "
            item = QListWidgetItem(f"{prefix}{channel.get('name', 'Unknown')}")
            item.setData(Qt.ItemDataRole.UserRole, channel)
            self.channels_list.addItem(item)
        
        self.channel_count.setText(f"{len(channels)} channels")
    
    def filter_channels(self, text):
        """Filter channels - search across ALL channels"""
        self.channels_list.clear()
        search_text = text.lower().strip()
        
        if not search_text:
            # Show category channels
            for channel in self.category_channels:
                stream_id = channel.get('stream_id')
                is_fav = self.favorites_manager and self.favorites_manager.is_favorite('channels', stream_id)
                prefix = "⭐ " if is_fav else "📺 "
                item = QListWidgetItem(f"{prefix}{channel.get('name', 'Unknown')}")
                item.setData(Qt.ItemDataRole.UserRole, channel)
                self.channels_list.addItem(item)
            self.channel_count.setText(f"{len(self.category_channels)} channels")
        else:
            # Search all channels
            matches = 0
            for channel in self.all_channels:
                channel_name = channel.get('name', '').lower()
                if search_text in channel_name:
                    stream_id = channel.get('stream_id')
                    is_fav = self.favorites_manager and self.favorites_manager.is_favorite('channels', stream_id)
                    prefix = "⭐ " if is_fav else "🔍 "
                    item = QListWidgetItem(f"{prefix}{channel.get('name', 'Unknown')}")
                    item.setData(Qt.ItemDataRole.UserRole, channel)
                    self.channels_list.addItem(item)
                    matches += 1
            self.channel_count.setText(f"{matches} results from all channels")
    
    def on_channel_selected(self, item):
        """Display channel info and EPG when channel is selected"""
        if not item:
            return
        
        channel_data = item.data(Qt.ItemDataRole.UserRole)
        if not channel_data:
            return
        
        self.current_channel = channel_data
        channel_name = channel_data.get('name', 'Unknown')
        
        # Update channel info
        self.channel_name.setText(channel_name)
        self.channel_info_label.setText("Loading program guide...")
        
        # Update channel logo/artwork
        logo_url = channel_data.get('stream_icon', '')
        if logo_url:
            self.load_channel_logo(logo_url)
        else:
            self.channel_logo.setPixmap(QPixmap())
            self.channel_logo.setText("📺")
        
        # Enable play buttons
        self.play_embedded_btn.setEnabled(True)
        self.open_external_btn.setEnabled(True)
        
        # Load EPG data using new EPG loader with 24-hour cache
        stream_id = channel_data.get('stream_id')
        if stream_id:
            self.epg_loading.setText("Loading...")
            self.epg_list.clear()
            
            # Start EPG loading thread with cache support
            self.epg_loader_thread = EPGLoaderThread(self.api, stream_id, self.epg_cache)
            self.epg_loader_thread.epg_loaded.connect(self.on_epg_loaded)
            self.epg_loader_thread.start()
        else:
            self.display_no_epg()
    
    def on_epg_loaded(self, epg_data):
        """Handle loaded EPG data"""
        self.epg_loading.setText("")
        self.epg_list.clear()
        
        # Check if from cache and show indicator
        if epg_data.get('cached'):
            self.epg_loading.setText("📦 24h Cache")
            self.epg_loading.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: 600;")
        else:
            self.epg_loading.setText("🔄 Fresh")
            self.epg_loading.setStyleSheet("color: #64b5f6; font-size: 11px; font-weight: 600;")
        
        epg = epg_data.get('epg', {})
        
        if not epg:
            self.display_no_epg()
            return
        
        # Parse EPG using EPGParser
        epg_listings = EPGParser.parse_epg_response(epg)
        
        if not epg_listings:
            self.display_no_epg()
            return
        
        # Display EPG entries
        program_count = 0
        for program in epg_listings[:30]:  # Limit to 30 programs
            if self.add_epg_item(program):
                program_count += 1
        
        if program_count > 0:
            cache_status = " (from 24h cache)" if epg_data.get('cached') else " (fresh from API)"
            self.channel_info_label.setText(f"Showing {program_count} programs{cache_status}")
        else:
            self.display_no_epg()
    
    def add_epg_item(self, program: dict) -> bool:
        """Add a professional EPG list item"""
        title = program.get('title', '')
        description = program.get('description', '')
        is_now = program.get('is_current', False)
        start_dt = program.get('start_datetime')
        end_dt = program.get('end_datetime')
        
        # Skip if no title
        if not title:
            return False
        
        # Format time
        time_str = EPGParser.format_time_range(start_dt, end_dt)
        
        # Create list item
        item = QListWidgetItem()
        
        # Build display text
        if is_now:
            display_text = f"🔴 NOW  {time_str}\n{title}"
            if description:
                desc_preview = description[:100] + "..." if len(description) > 100 else description
                display_text += f"\n{desc_preview}"
            item.setForeground(QColor("#4ade80"))
            font = QFont()
            font.setPointSize(11)
            font.setBold(True)
        else:
            display_text = f"       {time_str}\n{title}"
            if description:
                desc_preview = description[:80] + "..." if len(description) > 80 else description
                display_text += f"\n{desc_preview}"
            item.setForeground(QColor("#ffffff"))
            font = QFont()
            font.setPointSize(11)
        
        item.setText(display_text)
        item.setData(Qt.ItemDataRole.UserRole, program)
        item.setFont(font)
        
        self.epg_list.addItem(item)
        return True
    
    def display_no_epg(self):
        """Display message when no EPG is available"""
        self.epg_list.clear()
        item = QListWidgetItem("📋 No program guide available for this channel")
        item.setForeground(QColor("#95a5a6"))
        font = QFont()
        font.setPointSize(12)
        item.setFont(font)
        self.epg_list.addItem(item)
        self.channel_info_label.setText("Program guide not available")
        self.epg_loading.setText("")
    
    def load_channel_logo(self, url):
        """Load channel logo from URL"""
        if url:
            request = QNetworkRequest(QUrl(url))
            reply = self.network_manager.get(request)
            reply.finished.connect(lambda: self.on_logo_loaded(reply))
    
    def on_logo_loaded(self, reply):
        """Handle loaded logo"""
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = reply.readAll()
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio, 
                                             Qt.TransformationMode.SmoothTransformation)
                self.channel_logo.setPixmap(scaled_pixmap)
        reply.deleteLater()
    
    def play_selected_channel(self, fullscreen=True):
        """Play the selected channel – embedded or fullscreen depending on flag."""
        if not self.current_channel:
            return
        stream_id = self.current_channel.get('stream_id')
        channel_name = self.current_channel.get('name', 'Unknown')
        if not stream_id:
            return
        stream_url = self.api.get_stream_url(stream_id, 'live')
        if fullscreen:
            # Start embedded then immediately go fullscreen
            self._start_embedded_playback(stream_url, channel_name)
            self.embedded_player.go_fullscreen()
        else:
            self._start_embedded_playback(stream_url, channel_name)

    def play_channel(self, item, fullscreen=True):
        """Play selected channel – called from double-click or context menu."""
        if not item:
            return
        channel_data = item.data(Qt.ItemDataRole.UserRole)
        if channel_data:
            stream_id = channel_data.get('stream_id')
            channel_name = channel_data.get('name', 'Unknown')
            if stream_id:
                stream_url = self.api.get_stream_url(stream_id, 'live')
                self._start_embedded_playback(stream_url, channel_name)

    def play_channel_embedded(self):
        """Slot: play current channel embedded (triggered by ▶ Play button)."""
        if not self.current_channel:
            return
        stream_id = self.current_channel.get('stream_id')
        channel_name = self.current_channel.get('name', 'Unknown')
        if stream_id:
            stream_url = self.api.get_stream_url(stream_id, 'live')
            self._start_embedded_playback(stream_url, channel_name)

    def play_channel_external(self):
        """Slot: open current channel in external VLC (↗ Open in VLC button)."""
        if not self.current_channel:
            return
        stream_id = self.current_channel.get('stream_id')
        channel_name = self.current_channel.get('name', 'Unknown')
        if stream_id:
            stream_url = self.api.get_stream_url(stream_id, 'live')
            # Stop the embedded player first to avoid two streams running simultaneously
            self.embedded_player.stop()
            self.video_placeholder.show()
            self.stop_btn.setEnabled(False)
            self.fullscreen_btn.setEnabled(False)
            self.status_label.setText(f"↗ Playing in external VLC: {channel_name}")
            self.status_label.setStyleSheet("color: #f39c12; padding: 5px;")
            if not self.player.play_stream(stream_url, channel_name, False, 'live'):
                QMessageBox.critical(self, "VLC Error",
                                     "Could not launch VLC. Please make sure VLC Media Player is installed.")

    def _start_embedded_playback(self, stream_url: str, channel_name: str):
        """Internal helper: begin embedded playback and update UI."""
        self.embedded_player.play(stream_url, channel_name, 'live')
        self.video_placeholder.hide()
        self.stop_btn.setEnabled(True)
        self.fullscreen_btn.setEnabled(True)
        self.status_label.setText(f"▶ Now playing: {channel_name}")
        self.status_label.setStyleSheet("color: #2ecc71; padding: 5px;")

    def stop_playback(self):
        """Stop embedded playback and reset the video frame."""
        self.embedded_player.stop()
        self.video_placeholder.show()
        self.stop_btn.setEnabled(False)
        self.fullscreen_btn.setEnabled(False)
        self.status_label.setText("")

    def _on_mute_toggled(self):
        """Toggle mute and update the mute button icon."""
        is_muted = self.embedded_player.toggle_mute()
        self.mute_btn.setText("🔇" if is_muted else "🔊")