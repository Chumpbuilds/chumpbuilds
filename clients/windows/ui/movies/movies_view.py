"""
Movies View - 3-column layout with Categories, Movies, and Movie Details
Clean list format with merged artwork and plot section
Added Favorites functionality
Current Date and Time (UTC): 2025-11-15 19:32:07
Current User: covchump
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                            QListWidgetItem, QLabel, QPushButton,
                            QSplitter, QProgressBar, QTextEdit, QMessageBox, QFrame,
                            QScrollArea, QMenu, QSlider)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QPoint
from PyQt6.QtGui import QFont, QPixmap, QAction, QCursor
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from player.vlc_player import get_vlc_player
from player.mpv_player import get_embedded_mpv_player

# Add favorites import
try:
    from ..favorites.favorites_manager import get_favorites_manager
except ImportError:
    # Fallback if favorites module doesn't exist yet
    def get_favorites_manager():
        return None

class MoviesLoaderThread(QThread):
    categories_loaded = pyqtSignal(list)
    movies_loaded = pyqtSignal(list)
    all_movies_loaded = pyqtSignal(list)
    movie_info_loaded = pyqtSignal(dict)
    
    def __init__(self, api, load_type='categories', category_id=None, vod_id=None):
        super().__init__()
        self.api = api
        self.load_type = load_type
        self.category_id = category_id
        self.vod_id = vod_id
    
    def run(self):
        if self.load_type == 'categories':
            categories = self.api.get_vod_categories()
            self.categories_loaded.emit(categories)
        elif self.load_type == 'all_movies':
            movies = self.api.get_vod_streams(None)
            self.all_movies_loaded.emit(movies)
        elif self.load_type == 'movies':
            movies = self.api.get_vod_streams(self.category_id)
            self.movies_loaded.emit(movies)
        elif self.load_type == 'movie_info' and self.vod_id:
            info = self.api.get_vod_info(self.vod_id)
            self.movie_info_loaded.emit(info)

class MoviesView(QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.current_category = None
        self.current_movie = None
        self.player = get_vlc_player()
        self.all_movies = []
        self.category_movies = []
        self.stored_categories = []
        self.network_manager = QNetworkAccessManager()
        
        # Track current search text (set by header search bar)
        self._current_search_text = ""
        
        # Initialize favorites manager
        self.favorites_manager = get_favorites_manager()
        
        self.init_ui()
    
    def init_ui(self):
        # Main horizontal layout
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create three columns
        self.create_categories_column()
        self.create_movies_column()
        self.create_details_column()
        
        # Add columns to main layout with splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.categories_widget)
        splitter.addWidget(self.movies_widget)
        splitter.addWidget(self.details_widget)
        
        # Set column widths (25%, 25%, 50%)
        splitter.setSizes([300, 300, 600])
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
    
    def create_movies_column(self):
        """Create the movies column (25% width)"""
        self.movies_widget = QWidget()
        self.movies_widget.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                border-right: 1px solid #3a3a3a;
            }
        """)
        
        layout = QVBoxLayout(self.movies_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Title
        self.movies_title = QLabel("Movies")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        self.movies_title.setFont(title_font)
        self.movies_title.setStyleSheet("color: #e74c3c; padding: 5px;")
        layout.addWidget(self.movies_title)
        
        # Movies list - ADD CONTEXT MENU
        self.movies_list = QListWidget()
        self.movies_list.setStyleSheet("""
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
        self.movies_list.itemClicked.connect(self.on_movie_selected)
        self.movies_list.itemDoubleClicked.connect(self.play_movie)
        
        # ADD CONTEXT MENU FOR FAVORITES
        self.movies_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.movies_list.customContextMenuRequested.connect(self.show_movie_context_menu)
        
        layout.addWidget(self.movies_list)
        
        # Movie count label
        self.movie_count = QLabel("0 movies")
        self.movie_count.setStyleSheet("color: #95a5a6; font-size: 11px; padding: 5px;")
        layout.addWidget(self.movie_count)
        
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
    
    def show_movie_context_menu(self, position: QPoint):
        """Show context menu for movie with favorites option"""
        item = self.movies_list.itemAt(position)
        if not item:
            return
        
        movie_data = item.data(Qt.ItemDataRole.UserRole)
        if not movie_data:
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
        play_action = QAction("▶ Play Movie", self)
        play_action.triggered.connect(lambda: self.play_movie(item))
        menu.addAction(play_action)
        
        # Favorites actions
        if self.favorites_manager:
            menu.addSeparator()
            
            stream_id = movie_data.get('stream_id')
            is_favorite = self.favorites_manager.is_favorite('movies', stream_id)
            
            if is_favorite:
                remove_fav_action = QAction("❌ Remove from Favorites", self)
                remove_fav_action.triggered.connect(lambda: self.remove_from_favorites(movie_data))
                menu.addAction(remove_fav_action)
            else:
                add_fav_action = QAction("⭐ Add to Favorites", self)
                add_fav_action.triggered.connect(lambda: self.add_to_favorites(movie_data))
                menu.addAction(add_fav_action)
        
        menu.exec(QCursor.pos())
    
    def add_to_favorites(self, movie_data):
        """Add movie to favorites"""
        if self.favorites_manager and self.favorites_manager.add_favorite('movies', movie_data):
            self.status_label.setText(f"✓ Added to favorites: {movie_data.get('name', 'Unknown')}")
            self.status_label.setStyleSheet("color: #2ecc71; padding: 5px;")
            # Update main window favorites count if available
            if self.window() and hasattr(self.window(), 'update_favorites_count'):
                self.window().update_favorites_count()
        else:
            self.status_label.setText("Already in favorites")
            self.status_label.setStyleSheet("color: #f39c12; padding: 5px;")
    
    def remove_from_favorites(self, movie_data):
        """Remove movie from favorites"""
        stream_id = movie_data.get('stream_id')
        if self.favorites_manager and stream_id and self.favorites_manager.remove_favorite('movies', stream_id):
            self.status_label.setText(f"✓ Removed from favorites: {movie_data.get('name', 'Unknown')}")
            self.status_label.setStyleSheet("color: #e74c3c; padding: 5px;")
            # Update main window favorites count if available
            if self.window() and hasattr(self.window(), 'update_favorites_count'):
                self.window().update_favorites_count()
            # Refresh the current list
            if self._current_search_text:
                self.filter_movies(self._current_search_text)
            else:
                self.on_movies_loaded(self.category_movies)
    
    def create_details_column(self):
        """Create the movie details column (50% width) - with embedded VLC player"""
        self.details_widget = QWidget()
        self.details_widget.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
            }
        """)
        
        layout = QVBoxLayout(self.details_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # ── 1. Embedded video player frame ────────────────────────────────────
        self.video_frame = QFrame()
        self.video_frame.setStyleSheet("background-color: #000000; border-radius: 6px;")
        self.video_frame.setMinimumHeight(300)
        self.video_frame.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)

        self.video_placeholder = QLabel("🎬  Select a movie and click Play to start watching")
        self.video_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_placeholder.setWordWrap(True)
        self.video_placeholder.setStyleSheet("color: #666666; font-size: 13px; background: transparent;")

        _vf_layout = QVBoxLayout(self.video_frame)
        _vf_layout.setContentsMargins(10, 10, 10, 10)
        _vf_layout.addStretch()
        _vf_layout.addWidget(self.video_placeholder)
        _vf_layout.addStretch()

        layout.addWidget(self.video_frame, stretch=3)

        self.embedded_player = get_embedded_mpv_player(self.video_frame)

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
        self.play_embedded_btn.clicked.connect(self.play_movie_embedded)

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
        self.open_external_btn.clicked.connect(self.play_movie_external)

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

        # ── 3. Movie info scroll area ─────────────────────────────────────────
        movie_scroll = QScrollArea()
        movie_scroll.setWidgetResizable(True)
        movie_scroll.setStyleSheet("""
            QScrollArea {
                background-color: #2c3e50;
                border: none;
                border-radius: 10px;
            }
            QScrollBar:vertical {
                background-color: #34495e;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #3498db;
                border-radius: 5px;
            }
        """)
        
        # Content widget inside scroll area
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: transparent;")
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(20)
        
        # Header section with poster and title
        header_layout = QHBoxLayout()
        header_layout.setSpacing(20)
        
        # Movie poster
        self.movie_poster = QLabel()
        self.movie_poster.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignCenter)
        self.movie_poster.setFixedSize(140, 210)
        self.movie_poster.setStyleSheet("""
            QLabel {
                background-color: #34495e;
                border-radius: 8px;
            }
        """)
        self.movie_poster.setText("🎬")
        self.movie_poster.setScaledContents(True)
        poster_font = QFont()
        poster_font.setPointSize(40)
        self.movie_poster.setFont(poster_font)
        header_layout.addWidget(self.movie_poster)
        
        # Title and metadata section
        title_section = QVBoxLayout()
        title_section.setSpacing(10)
        
        # Movie title
        self.movie_name = QLabel("No Movie Selected")
        name_font = QFont()
        name_font.setPointSize(18)
        name_font.setBold(True)
        self.movie_name.setFont(name_font)
        self.movie_name.setStyleSheet("color: white; background: transparent;")
        self.movie_name.setWordWrap(True)
        title_section.addWidget(self.movie_name)
        
        # Quick info with icons (only shown if data exists)
        self.movie_quick_info = QLabel("")
        self.movie_quick_info.setStyleSheet("color: rgba(255, 255, 255, 0.8); font-size: 13px; background: transparent;")
        self.movie_quick_info.setWordWrap(True)
        title_section.addWidget(self.movie_quick_info)
        
        # Loading indicator
        self.movie_loading_label = QLabel("")
        self.movie_loading_label.setStyleSheet("color: #64b5f6; font-size: 11px; background: transparent;")
        title_section.addWidget(self.movie_loading_label)
        
        title_section.addStretch()
        header_layout.addLayout(title_section, 1)
        
        content_layout.addLayout(header_layout)
        
        # Separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: rgba(255, 255, 255, 0.1); max-height: 1px;")
        content_layout.addWidget(separator)
        
        # Movie information section
        self.movie_info = QTextEdit()
        self.movie_info.setReadOnly(True)
        self.movie_info.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                color: white;
                border: none;
                padding: 0px;
            }
        """)
        self.movie_info.setMinimumHeight(300)
        content_layout.addWidget(self.movie_info)
        
        movie_scroll.setWidget(scroll_content)
        layout.addWidget(movie_scroll, stretch=2)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #2ecc71; padding: 5px;")
        layout.addWidget(self.status_label)
    
    def load_data(self):
        """Load categories and all movies"""
        self.progress_bar.show()
        # Load categories
        self.loader_thread = MoviesLoaderThread(self.api, 'categories')
        self.loader_thread.categories_loaded.connect(self.on_categories_loaded)
        self.loader_thread.start()
        
        # Load all movies for search
        self.all_loader_thread = MoviesLoaderThread(self.api, 'all_movies')
        self.all_loader_thread.all_movies_loaded.connect(self.on_all_movies_loaded)
        self.all_loader_thread.start()
    
    def on_all_movies_loaded(self, movies):
        """Store all movies for search functionality"""
        self.all_movies = movies
    
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
        
        # Update movies title
        self.movies_title.setText(f"Movies - {category_name}")
        
        self.progress_bar.show()
        self.loader_thread = MoviesLoaderThread(self.api, 'movies', category_id)
        self.loader_thread.movies_loaded.connect(self.on_movies_loaded)
        self.loader_thread.start()
    
    def on_movies_loaded(self, movies):
        self.progress_bar.hide()
        self.movies_list.clear()
        self.category_movies = movies
        
        for movie in movies:
            # Add favorite indicator if applicable
            stream_id = movie.get('stream_id')
            is_fav = self.favorites_manager and self.favorites_manager.is_favorite('movies', stream_id)
            prefix = "⭐ " if is_fav else "🎬 "
            item = QListWidgetItem(f"{prefix}{movie.get('name', 'Unknown')}")
            item.setData(Qt.ItemDataRole.UserRole, movie)
            self.movies_list.addItem(item)
        
        self.movie_count.setText(f"{len(movies)} movies")
    
    def filter_movies(self, text):
        """Filter movies - search across ALL movies"""
        self._current_search_text = text
        self.movies_list.clear()
        search_text = text.lower().strip()
        
        if not search_text:
            # Show category movies
            for movie in self.category_movies:
                stream_id = movie.get('stream_id')
                is_fav = self.favorites_manager and self.favorites_manager.is_favorite('movies', stream_id)
                prefix = "⭐ " if is_fav else "🎬 "
                item = QListWidgetItem(f"{prefix}{movie.get('name', 'Unknown')}")
                item.setData(Qt.ItemDataRole.UserRole, movie)
                self.movies_list.addItem(item)
            self.movie_count.setText(f"{len(self.category_movies)} movies")
        else:
            # Search all movies
            matches = 0
            for movie in self.all_movies:
                movie_name = movie.get('name', '').lower()
                if search_text in movie_name:
                    stream_id = movie.get('stream_id')
                    is_fav = self.favorites_manager and self.favorites_manager.is_favorite('movies', stream_id)
                    prefix = "⭐ " if is_fav else "🔍 "
                    item = QListWidgetItem(f"{prefix}{movie.get('name', 'Unknown')}")
                    item.setData(Qt.ItemDataRole.UserRole, movie)
                    self.movies_list.addItem(item)
                    matches += 1
            self.movie_count.setText(f"{matches} results from all movies")
    
    def on_movie_selected(self, item):
        """Display movie info when movie is selected - HIDE N/A VALUES"""
        if not item:
            return
        
        movie_data = item.data(Qt.ItemDataRole.UserRole)
        if not movie_data:
            return
        
        self.current_movie = movie_data
        movie_name = movie_data.get('name', 'Unknown')
        
        # Update movie info
        self.movie_name.setText(movie_name)
        self.movie_loading_label.setText("Loading movie details...")
        
        # Build quick info - ONLY show values that exist (not N/A)
        info_parts = []
        
        # Check if favorited
        stream_id = movie_data.get('stream_id')
        if self.favorites_manager and self.favorites_manager.is_favorite('movies', stream_id):
            info_parts.append("⭐ Favorited")
        
        rating = movie_data.get('rating', movie_data.get('rating_5based', ''))
        if rating and rating != 'N/A' and rating != '0' and rating != '0.0':
            info_parts.append(f"⭐ {rating}")
        
        year = movie_data.get('year', movie_data.get('releaseDate', ''))
        if year and year != 'N/A' and year != '0':
            info_parts.append(f"📅 {year}")
        
        duration = movie_data.get('duration', '')
        if duration and duration != 'N/A':
            info_parts.append(f"⏱️ {duration}")
        
        # Set quick info only if we have data
        if info_parts:
            self.movie_quick_info.setText(" • ".join(info_parts))
        else:
            self.movie_quick_info.setText("")
        
        # Update movie poster
        poster_url = movie_data.get('stream_icon', movie_data.get('cover', ''))
        if poster_url:
            self.load_movie_poster(poster_url)
        else:
            self.movie_poster.setPixmap(QPixmap())
            self.movie_poster.setText("🎬")
        
        # Enable play buttons
        self.play_embedded_btn.setEnabled(True)
        self.open_external_btn.setEnabled(True)
        
        # Fetch detailed movie info with plot
        vod_id = movie_data.get('stream_id')
        if vod_id:
            self.info_loader_thread = MoviesLoaderThread(self.api, 'movie_info', vod_id=vod_id)
            self.info_loader_thread.movie_info_loaded.connect(self.on_movie_info_loaded)
            self.info_loader_thread.start()
        else:
            # Show basic info if no vod_id
            self.display_basic_movie_info(movie_data)
    
    def on_movie_info_loaded(self, movie_info):
        """Handle detailed movie info with plot"""
        self.movie_loading_label.setText("")
        
        if not movie_info or 'info' not in movie_info:
            # Fallback to basic info
            self.display_basic_movie_info(self.current_movie)
            return
        
        info = movie_info.get('info', {})
        movie_data = movie_info.get('movie_data', {})
        
        # Extract plot/description
        plot = (info.get('plot') or 
                info.get('description') or 
                info.get('desc') or 
                movie_data.get('plot') or
                movie_data.get('description') or
                'No plot information available.')
        
        # Get additional details - HIDE N/A VALUES
        details_html = ""
        
        director = info.get('director', '')
        if director and director != 'N/A':
            details_html += f"<tr><td style='color: #95a5a6; width: 30%;'>Director:</td><td>{director}</td></tr>"
        
        cast = info.get('cast', info.get('actors', ''))
        if cast and cast != 'N/A':
            details_html += f"<tr><td style='color: #95a5a6;'>Cast:</td><td>{cast}</td></tr>"
        
        genre = info.get('genre', '')
        if genre and genre != 'N/A':
            details_html += f"<tr><td style='color: #95a5a6;'>Genre:</td><td>{genre}</td></tr>"
        
        country = info.get('country', '')
        if country and country != 'N/A':
            details_html += f"<tr><td style='color: #95a5a6;'>Country:</td><td>{country}</td></tr>"
        
        # Format duration
        duration_secs = info.get('duration_secs', info.get('duration', ''))
        if duration_secs and duration_secs != 'N/A':
            try:
                mins = int(duration_secs) // 60
                duration_str = f"{mins} minutes"
                details_html += f"<tr><td style='color: #95a5a6;'>Duration:</td><td>{duration_str}</td></tr>"
            except:
                if str(duration_secs) != '0':
                    details_html += f"<tr><td style='color: #95a5a6;'>Duration:</td><td>{duration_secs}</td></tr>"
        
        # Get extension
        extension = (self.current_movie.get('container_extension') or 
                    info.get('container_extension') or 
                    'mp4')
        details_html += f"<tr><td style='color: #95a5a6;'>Format:</td><td>{extension.upper()}</td></tr>"
        
        # Build detailed info HTML
        info_html = f"""
        <h3 style="color: #3498db; margin-bottom: 10px; margin-top: 0;">Plot Synopsis</h3>
        <p style="line-height: 1.6; margin-bottom: 20px;">{plot}</p>
        """
        
        # Only add details section if we have details to show
        if details_html:
            info_html += f"""
            <h3 style="color: #3498db; margin-bottom: 10px;">Details</h3>
            <table style="width: 100%; line-height: 1.8;">
                {details_html}
            </table>
            """
        
        self.movie_info.setHtml(info_html)
        print(f"[Movies] Loaded detailed info for: {self.current_movie.get('name')}")
    
    def display_basic_movie_info(self, movie_data):
        """Display basic movie info when detailed info is not available"""
        self.movie_loading_label.setText("")
        
        # Try to get plot from basic data
        plot = (movie_data.get('plot') or 
                movie_data.get('description') or 
                movie_data.get('desc') or
                'No plot information available.')
        
        extension = movie_data.get('container_extension', 'mp4')
        
        # Build details table - HIDE N/A
        details_html = ""
        
        year = movie_data.get('year', '')
        if year and year != 'N/A' and year != '0':
            details_html += f"<tr><td style='color: #95a5a6; width: 30%;'>Year:</td><td>{year}</td></tr>"
        
        rating = movie_data.get('rating', '')
        if rating and rating != 'N/A' and rating != '0' and rating != '0.0':
            details_html += f"<tr><td style='color: #95a5a6;'>Rating:</td><td>{rating}</td></tr>"
        
        duration = movie_data.get('duration', '')
        if duration and duration != 'N/A':
            details_html += f"<tr><td style='color: #95a5a6;'>Duration:</td><td>{duration}</td></tr>"
        
        details_html += f"<tr><td style='color: #95a5a6;'>Format:</td><td>{extension.upper()}</td></tr>"
        
        info_html = f"""
        <h3 style="color: #3498db; margin-bottom: 10px; margin-top: 0;">Description</h3>
        <p style="line-height: 1.6; margin-bottom: 20px;">{plot}</p>
        """
        
        if details_html:
            info_html += f"""
            <h3 style="color: #3498db; margin-bottom: 10px;">Details</h3>
            <table style="width: 100%; line-height: 1.8;">
                {details_html}
            </table>
            """
        
        info_html += """
        <p style="color: #95a5a6; margin-top: 15px; font-size: 11px;">
        <i>Detailed information not available for this movie.</i>
        </p>
        """
        
        self.movie_info.setHtml(info_html)
    
    def load_movie_poster(self, url):
        """Load movie poster from URL"""
        if url:
            request = QNetworkRequest(QUrl(url))
            reply = self.network_manager.get(request)
            reply.finished.connect(lambda: self.on_poster_loaded(reply))
    
    def on_poster_loaded(self, reply):
        """Handle loaded poster"""
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = reply.readAll()
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(140, 210, Qt.AspectRatioMode.KeepAspectRatio, 
                                             Qt.TransformationMode.SmoothTransformation)
                self.movie_poster.setPixmap(scaled_pixmap)
        reply.deleteLater()
    
    def play_movie(self, item, column=None):
        """Play selected movie in embedded player (called from double-click)."""
        if not item:
            return
        movie_data = item.data(Qt.ItemDataRole.UserRole)
        if movie_data:
            stream_id = movie_data.get('stream_id')
            movie_name = movie_data.get('name', 'Unknown')
            if stream_id:
                stream_url = self.api.get_stream_url(stream_id, 'movie', stream_data=movie_data)
                self._start_embedded_playback(stream_url, movie_name)

    def play_movie_embedded(self):
        """Slot: play current movie embedded (triggered by ▶ Play button)."""
        if not self.current_movie:
            return
        stream_id = self.current_movie.get('stream_id')
        movie_name = self.current_movie.get('name', 'Unknown')
        if stream_id:
            stream_url = self.api.get_stream_url(stream_id, 'movie', stream_data=self.current_movie)
            self._start_embedded_playback(stream_url, movie_name)

    def play_movie_external(self):
        """Slot: open current movie in external VLC (↗ Open in VLC button)."""
        if not self.current_movie:
            return
        stream_id = self.current_movie.get('stream_id')
        movie_name = self.current_movie.get('name', 'Unknown')
        if stream_id:
            stream_url = self.api.get_stream_url(stream_id, 'movie', stream_data=self.current_movie)
            self.embedded_player.stop()
            self.video_placeholder.show()
            self.stop_btn.setEnabled(False)
            self.fullscreen_btn.setEnabled(False)
            self.status_label.setText(f"↗ Playing in external VLC: {movie_name}")
            self.status_label.setStyleSheet("color: #f39c12; padding: 5px;")
            if not self.player.play_stream(stream_url, movie_name, False, 'movie'):
                QMessageBox.critical(self, "VLC Error",
                                     "Could not launch VLC. Please make sure VLC Media Player is installed.")

    def _start_embedded_playback(self, stream_url: str, movie_name: str):
        """Internal helper: begin embedded playback and update UI.

        Starts playback of *stream_url* (with content type 'movie') in the
        embedded player, hides the placeholder, enables Stop/Fullscreen buttons,
        and updates the status label to show the playing movie name.
        """
        self.embedded_player.play(stream_url, movie_name, 'movie')
        self.video_placeholder.hide()
        self.stop_btn.setEnabled(True)
        self.fullscreen_btn.setEnabled(True)
        self.status_label.setText(f"▶ Now playing: {movie_name}")
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
