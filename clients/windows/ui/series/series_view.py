"""
Series View - 3-column layout with Categories, Series, and Episodes
Single unified box with maximum episode space
Added Favorites functionality
Current Date and Time (UTC): 2025-11-15 19:41:30
Current User: covchump
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                            QListWidgetItem, QLabel, QPushButton,
                            QSplitter, QProgressBar, QTextEdit, QTreeWidget,
                            QTreeWidgetItem, QMessageBox, QFrame, QScrollArea, QMenu)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QPoint
from PyQt6.QtGui import QFont, QPixmap, QAction, QCursor
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from player.vlc_player import get_vlc_player

# Add favorites import
try:
    from ..favorites.favorites_manager import get_favorites_manager
except ImportError:
    # Fallback if favorites module doesn't exist yet
    def get_favorites_manager():
        return None

class SeriesLoaderThread(QThread):
    categories_loaded = pyqtSignal(list)
    series_loaded = pyqtSignal(list)
    all_series_loaded = pyqtSignal(list)
    series_info_loaded = pyqtSignal(dict)
    
    def __init__(self, api, load_type='categories', category_id=None, series_id=None):
        super().__init__()
        self.api = api
        self.load_type = load_type
        self.category_id = category_id
        self.series_id = series_id
    
    def run(self):
        if self.load_type == 'categories':
            categories = self.api.get_series_categories()
            self.categories_loaded.emit(categories)
        elif self.load_type == 'all_series':
            series = self.api.get_series(None)
            self.all_series_loaded.emit(series)
        elif self.load_type == 'series':
            series = self.api.get_series(self.category_id)
            self.series_loaded.emit(series)
        elif self.load_type == 'series_info':
            info = self.api.get_series_info(self.series_id)
            self.series_info_loaded.emit(info)

class SeriesView(QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.current_category = None
        self.current_series = None
        self.player = get_vlc_player()
        self.all_series = []
        self.category_series = []
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
        self.create_series_column()
        self.create_episodes_column()
        
        # Add columns to main layout with splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.categories_widget)
        splitter.addWidget(self.series_widget)
        splitter.addWidget(self.episodes_widget)
        
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
    
    def create_series_column(self):
        """Create the series column (25% width)"""
        self.series_widget = QWidget()
        self.series_widget.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                border-right: 1px solid #3a3a3a;
            }
        """)
        
        layout = QVBoxLayout(self.series_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Title
        self.series_title = QLabel("Series")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        self.series_title.setFont(title_font)
        self.series_title.setStyleSheet("color: #e74c3c; padding: 5px;")
        layout.addWidget(self.series_title)
        
        # Series list - ADD CONTEXT MENU
        self.series_list = QListWidget()
        self.series_list.setStyleSheet("""
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
        self.series_list.itemClicked.connect(self.on_series_selected)
        
        # ADD CONTEXT MENU FOR FAVORITES
        self.series_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.series_list.customContextMenuRequested.connect(self.show_series_context_menu)
        
        layout.addWidget(self.series_list)
        
        # Series count label
        self.series_count = QLabel("0 series")
        self.series_count.setStyleSheet("color: #95a5a6; font-size: 11px; padding: 5px;")
        layout.addWidget(self.series_count)
        
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
    
    def show_series_context_menu(self, position: QPoint):
        """Show context menu for series with favorites option"""
        item = self.series_list.itemAt(position)
        if not item:
            return
        
        series_data = item.data(Qt.ItemDataRole.UserRole)
        if not series_data:
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
        
        # View episodes action
        view_action = QAction("📼 View Episodes", self)
        view_action.triggered.connect(lambda: self.on_series_selected(item))
        menu.addAction(view_action)
        
        # Favorites actions
        if self.favorites_manager:
            menu.addSeparator()
            
            series_id = series_data.get('series_id')
            is_favorite = self.favorites_manager.is_favorite('series', str(series_id))
            
            if is_favorite:
                remove_fav_action = QAction("❌ Remove from Favorites", self)
                remove_fav_action.triggered.connect(lambda: self.remove_from_favorites(series_data))
                menu.addAction(remove_fav_action)
            else:
                add_fav_action = QAction("⭐ Add to Favorites", self)
                add_fav_action.triggered.connect(lambda: self.add_to_favorites(series_data))
                menu.addAction(add_fav_action)
        
        menu.exec(QCursor.pos())

    def add_to_favorites(self, series_data):
        """Add series to favorites"""
        if self.favorites_manager and self.favorites_manager.add_favorite('series', series_data):
            self.status_label.setText(f"✓ Added to favorites: {series_data.get('name', 'Unknown')}")
            self.status_label.setStyleSheet("color: #2ecc71; padding: 5px;")
            if self.window() and hasattr(self.window(), 'update_favorites_count'):
                self.window().update_favorites_count()
            self.refresh_current_list()
        else:
            self.status_label.setText("Already in favorites")
            self.status_label.setStyleSheet("color: #f39c12; padding: 5px;")

    def remove_from_favorites(self, series_data):
        """Remove series from favorites"""
        series_id = series_data.get('series_id')
        if self.favorites_manager and series_id and self.favorites_manager.remove_favorite('series', str(series_id)):
            self.status_label.setText(f"✓ Removed from favorites: {series_data.get('name', 'Unknown')}")
            self.status_label.setStyleSheet("color: #e74c3c; padding: 5px;")
            if self.window() and hasattr(self.window(), 'update_favorites_count'):
                self.window().update_favorites_count()
            self.refresh_current_list()
            
    def refresh_current_list(self):
        """Refresh the current series list to show favorite indicators."""
        if self._current_search_text.strip():
            self.filter_series(self._current_search_text)
        else:
            self.on_series_loaded(self.category_series)

    def create_episodes_column(self):
        """Create episodes column - NO HEADING, NO SEPARATOR"""
        self.episodes_widget = QWidget()
        self.episodes_widget.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
            }
        """)
        
        layout = QVBoxLayout(self.episodes_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Single scrollable container for everything
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
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
        
        # Content widget
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: transparent;")
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)  # Reduced spacing
        
        # Header with artwork and info (horizontal layout)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(20)
        
        # Poster
        self.series_poster = QLabel()
        self.series_poster.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignCenter)
        self.series_poster.setFixedSize(140, 210)
        self.series_poster.setStyleSheet("""
            QLabel {
                background-color: #34495e;
                border-radius: 8px;
            }
        """)
        self.series_poster.setText("📼")
        self.series_poster.setScaledContents(True)
        poster_font = QFont()
        poster_font.setPointSize(40)
        self.series_poster.setFont(poster_font)
        header_layout.addWidget(self.series_poster)
        
        # Info section (title, rating, plot)
        info_section = QVBoxLayout()
        info_section.setSpacing(10)
        
        # Series name
        self.series_name = QLabel("No Series Selected")
        name_font = QFont()
        name_font.setPointSize(18)
        name_font.setBold(True)
        self.series_name.setFont(name_font)
        self.series_name.setStyleSheet("color: white; background: transparent;")
        self.series_name.setWordWrap(True)
        info_section.addWidget(self.series_name)
        
        # Quick info (rating, year)
        self.series_quick_info = QLabel("")
        self.series_quick_info.setStyleSheet("color: rgba(255, 255, 255, 0.8); font-size: 13px; background: transparent;")
        self.series_quick_info.setWordWrap(True)
        info_section.addWidget(self.series_quick_info)
        
        # Loading indicator
        self.series_loading_label = QLabel("")
        self.series_loading_label.setStyleSheet("color: #64b5f6; font-size: 11px; background: transparent;")
        info_section.addWidget(self.series_loading_label)
        
        # Plot
        self.series_info = QTextEdit()
        self.series_info.setReadOnly(True)
        self.series_info.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                color: white;
                border: none;
                padding: 0px;
            }
        """)
        self.series_info.setMaximumHeight(150)
        info_section.addWidget(self.series_info)
        
        header_layout.addLayout(info_section, 1)
        content_layout.addLayout(header_layout)
        
        # Episodes tree - NO HEADING, NO SEPARATOR
        self.episodes_tree = QTreeWidget()
        self.episodes_tree.setHeaderHidden(True)  # Hide the header
        self.episodes_tree.setStyleSheet("""
            QTreeWidget {
                background-color: rgba(52, 73, 94, 0.3);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 5px;
            }
            QTreeWidget::item {
                padding: 8px;
                border: none;
            }
            QTreeWidget::item:selected {
                background-color: #3498db;
            }
            QTreeWidget::item:hover {
                background-color: #34495e;
            }
        """)
        self.episodes_tree.itemDoubleClicked.connect(self.play_episode)
        self.episodes_tree.setMinimumHeight(400)
        content_layout.addWidget(self.episodes_tree)
        
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)
        
        # Play controls (outside scroll area)
        controls_layout = QHBoxLayout()
        
        self.play_button = QPushButton("▶ Play Episode (Fullscreen)")
        self.play_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 12px 20px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.play_button.clicked.connect(lambda: self.play_selected_episode(True))
        self.play_button.setEnabled(False)
        
        self.play_windowed_button = QPushButton("▶ Play (Windowed)")
        self.play_windowed_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 12px 20px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.play_windowed_button.clicked.connect(lambda: self.play_selected_episode(False))
        self.play_windowed_button.setEnabled(False)
        
        controls_layout.addWidget(self.play_button)
        controls_layout.addWidget(self.play_windowed_button)
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #2ecc71; padding: 5px;")
        layout.addWidget(self.status_label)
    
    def load_data(self):
        """Load categories and all series"""
        self.progress_bar.show()
        # Load categories
        self.loader_thread = SeriesLoaderThread(self.api, 'categories')
        self.loader_thread.categories_loaded.connect(self.on_categories_loaded)
        self.loader_thread.start()
        
        # Load all series for search
        self.all_loader_thread = SeriesLoaderThread(self.api, 'all_series')
        self.all_loader_thread.all_series_loaded.connect(self.on_all_series_loaded)
        self.all_loader_thread.start()
    
    def on_all_series_loaded(self, series):
        """Store all series for search functionality"""
        self.all_series = series if series else []
    
    def on_categories_loaded(self, categories):
        self.progress_bar.hide()
        self.categories_list.clear()
        self.stored_categories = categories if categories else []
        
        for category in self.stored_categories:
            item = QListWidgetItem(f"📁 {category.get('category_name', 'Unknown')}")
            item.setData(Qt.ItemDataRole.UserRole, category.get('category_id'))
            self.categories_list.addItem(item)
        
        self.category_count.setText(f"{len(self.stored_categories)} categories")
        
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
        
        # Update series title
        self.series_title.setText(f"Series - {category_name}")
        
        self.progress_bar.show()
        self.loader_thread = SeriesLoaderThread(self.api, 'series', category_id)
        self.loader_thread.series_loaded.connect(self.on_series_loaded)
        self.loader_thread.start()
    
    def on_series_loaded(self, series):
        self.progress_bar.hide()
        self.series_list.clear()
        self.category_series = series if series else []
        
        for show in self.category_series:
            series_id = show.get('series_id')
            is_fav = self.favorites_manager and self.favorites_manager.is_favorite('series', str(series_id))
            prefix = "⭐ " if is_fav else "📼 "
            item = QListWidgetItem(f"{prefix}{show.get('name', 'Unknown')}")
            item.setData(Qt.ItemDataRole.UserRole, show)
            self.series_list.addItem(item)
        
        self.series_count.setText(f"{len(self.category_series)} series")
    
    def filter_series(self, text):
        """Filter series - search across ALL series"""
        self._current_search_text = text
        self.series_list.clear()
        search_text = text.lower().strip()
        
        if not search_text:
            # Show category series
            for show in self.category_series:
                series_id = show.get('series_id')
                is_fav = self.favorites_manager and self.favorites_manager.is_favorite('series', str(series_id))
                prefix = "⭐ " if is_fav else "📼 "
                item = QListWidgetItem(f"{prefix}{show.get('name', 'Unknown')}")
                item.setData(Qt.ItemDataRole.UserRole, show)
                self.series_list.addItem(item)
            self.series_count.setText(f"{len(self.category_series)} series")
        else:
            # Search all series
            matches = 0
            if self.all_series:
                for show in self.all_series:
                    show_name = show.get('name', '').lower()
                    if search_text in show_name:
                        series_id = show.get('series_id')
                        is_fav = self.favorites_manager and self.favorites_manager.is_favorite('series', str(series_id))
                        prefix = "⭐ " if is_fav else "🔍 "
                        item = QListWidgetItem(f"{prefix}{show.get('name', 'Unknown')}")
                        item.setData(Qt.ItemDataRole.UserRole, show)
                        self.series_list.addItem(item)
                        matches += 1
            self.series_count.setText(f"{matches} results from all series")

    def on_series_selected(self, item):
        """Display series info and load episodes"""
        if not item:
            return
        
        series_data = item.data(Qt.ItemDataRole.UserRole)
        if not series_data:
            return
        
        self.current_series = series_data
        series_id = series_data.get('series_id')
        series_name = series_data.get('name', 'Unknown')
        
        # Update series info
        self.series_name.setText(series_name)
        self.series_loading_label.setText("Loading series details...")
        
        # Build quick info - ONLY show values that exist (not N/A)
        info_parts = []
        
        if self.favorites_manager and self.favorites_manager.is_favorite('series', str(series_id)):
            info_parts.append("⭐ Favorited")
        
        rating = series_data.get('rating', series_data.get('rating_5based', ''))
        if rating and rating != 'N/A' and rating != '0' and rating != '0.0':
            info_parts.append(f"⭐ {rating}")
        
        year = series_data.get('year', series_data.get('releaseDate', ''))
        if year and year != 'N/A' and year != '0':
            info_parts.append(f"📅 {year}")
        
        # Set quick info only if we have data
        if info_parts:
            self.series_quick_info.setText(" • ".join(info_parts))
        else:
            self.series_quick_info.setText("")
        
        # Update series poster
        poster_url = series_data.get('cover', series_data.get('stream_icon', ''))
        if poster_url:
            self.load_series_poster(poster_url)
        else:
            self.series_poster.setPixmap(QPixmap())
            self.series_poster.setText("📼")
        
        # Load episodes
        if series_id:
            self.progress_bar.show()
            self.loader_thread = SeriesLoaderThread(self.api, 'series_info', series_id=series_id)
            self.loader_thread.series_info_loaded.connect(self.on_series_info_loaded)
            self.loader_thread.start()
    
    def load_series_poster(self, url):
        """Load series poster from URL"""
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
                self.series_poster.setPixmap(scaled_pixmap)
        reply.deleteLater()
    
    def on_series_info_loaded(self, info):
        """Display series plot and episodes"""
        self.progress_bar.hide()
        self.series_loading_label.setText("")
        self.episodes_tree.clear()
        
        if not info:
            self.series_info.setPlainText("No information available for this series.")
            return
        
        # Extract and display plot
        series_info_data = info.get('info', {})
        plot = (series_info_data.get('plot') or 
                series_info_data.get('description') or 
                series_info_data.get('desc') or
                self.current_series.get('plot') or
                self.current_series.get('description') or
                'No plot information available.')
        
        # Get additional details
        details_parts = []
        
        genre = series_info_data.get('genre', '')
        if genre and genre != 'N/A':
            details_parts.append(f"<b>Genre:</b> {genre}")
        
        cast = series_info_data.get('cast', series_info_data.get('actors', ''))
        if cast and cast != 'N/A':
            details_parts.append(f"<b>Cast:</b> {cast}")
        
        director = series_info_data.get('director', '')
        if director and director != 'N/A':
            details_parts.append(f"<b>Director:</b> {director}")
        
        # Build plot HTML
        info_html = f"""
        <h3 style="color: #3498db; margin-bottom: 10px; margin-top: 0;">Plot Synopsis</h3>
        <p style='line-height: 1.6; margin-bottom: 15px;'>{plot}</p>
        """
        
        if details_parts:
            info_html += f"<p style='font-size: 12px; color: #95a5a6;'>{' • '.join(details_parts)}</p>"
        
        self.series_info.setHtml(info_html)
        
        # Handle different possible data structures
        episodes_data = None
        
        if 'episodes' in info:
            episodes_data = info['episodes']
        elif 'seasons' in info:
            self.process_seasons_data(info['seasons'])
            return
        
        if not episodes_data:
            return
        
        # Process episodes based on data type
        if isinstance(episodes_data, dict):
            self.process_episodes_dict(episodes_data)
        elif isinstance(episodes_data, list):
            self.process_episodes_list(episodes_data)
        
        # Enable play buttons if episodes loaded
        if self.episodes_tree.topLevelItemCount() > 0:
            self.play_button.setEnabled(True)
            self.play_windowed_button.setEnabled(True)
    
    def process_episodes_dict(self, episodes):
        """Process episodes when they're in dictionary format"""
        seasons = {}
        for episode_id, episode_data in episodes.items():
            if isinstance(episode_data, dict):
                season_num = episode_data.get('season', 1)
                if season_num not in seasons:
                    seasons[season_num] = []
                seasons[season_num].append(episode_data)
            elif isinstance(episode_data, list):
                for ep in episode_data:
                    if isinstance(ep, dict):
                        season_num = ep.get('season', 1)
                        if season_num not in seasons:
                            seasons[season_num] = []
                        seasons[season_num].append(ep)
        
        self.add_seasons_to_tree(seasons)
    
    def process_episodes_list(self, episodes):
        """Process episodes when they're in list format"""
        seasons = {}
        for episode_data in episodes:
            if isinstance(episode_data, dict):
                season_num = episode_data.get('season', 1)
                if season_num not in seasons:
                    seasons[season_num] = []
                seasons[season_num].append(episode_data)
        
        self.add_seasons_to_tree(seasons)
    
    def process_seasons_data(self, seasons_data):
        """Process when data is already organized by seasons"""
        if isinstance(seasons_data, dict):
            seasons = {}
            for season_key, episodes in seasons_data.items():
                try:
                    if isinstance(season_key, str):
                        season_num = int(''.join(filter(str.isdigit, season_key)) or '1')
                    else:
                        season_num = int(season_key)
                except:
                    season_num = 1
                
                if isinstance(episodes, list):
                    seasons[season_num] = episodes
                elif isinstance(episodes, dict):
                    seasons[season_num] = list(episodes.values())
            
            self.add_seasons_to_tree(seasons)
    
    def add_seasons_to_tree(self, seasons):
        """Add seasons and episodes to the tree widget"""
        for season_num in sorted(seasons.keys()):
            season_item = QTreeWidgetItem(self.episodes_tree)
            season_item.setText(0, f"📁 Season {season_num}")
            season_item.setExpanded(True)
            
            # Sort episodes by episode number
            season_episodes = sorted(seasons[season_num], 
                                    key=lambda x: x.get('episode_num', 0) if isinstance(x, dict) else 0)
            
            for episode in season_episodes:
                if isinstance(episode, dict):
                    episode_item = QTreeWidgetItem(season_item)
                    episode_num = episode.get('episode_num', '?')
                    episode_title = episode.get('title', episode.get('name', 'Unknown'))
                    episode_item.setText(0, f"▶ Episode {episode_num}: {episode_title}")
                    episode_item.setData(0, Qt.ItemDataRole.UserRole, episode)
    
    def play_selected_episode(self, fullscreen=True):
        """Play the selected episode"""
        current_item = self.episodes_tree.currentItem()
        if current_item and current_item.parent():
            self.play_episode(current_item, 0, fullscreen)
    
    def play_episode(self, item, column, fullscreen=True):
        """Play selected episode in external VLC"""
        if not item or not item.parent():
            return
        
        episode_data = item.data(0, Qt.ItemDataRole.UserRole)
        if episode_data and self.current_series:
            series_id = self.current_series.get('series_id')
            series_name = self.current_series.get('name', 'Unknown Series')
            
            season_num = episode_data.get('season', episode_data.get('season_num', 1))
            episode_num = episode_data.get('episode_num', episode_data.get('episode', '?'))
            episode_title = episode_data.get('title', episode_data.get('name', 'Unknown Episode'))
            
            container_extension = (episode_data.get('container_extension') or 
                                 episode_data.get('extension') or 
                                 episode_data.get('ext') or 
                                 'mp4')
            
            episode_id = episode_data.get('id', episode_data.get('episode_id'))
            
            full_title = f"{series_name} - S{season_num:02d}E{episode_num:02d} - {episode_title}"
            
            if series_id:
                if episode_id:
                    stream_url = f"{self.api.base_url}/series/{self.api.username}/{self.api.password}/{episode_id}.{container_extension}"
                else:
                    # Fallback if episode ID is missing (less common)
                    stream_url = f"{self.api.base_url}/series/{self.api.username}/{self.api.password}/{series_id}.{container_extension}"
                
                if self.player.play_stream(stream_url, full_title, fullscreen, 'series'):
                    self.status_label.setText(f"✓ Now playing: {full_title}")
                else:
                    QMessageBox.critical(self, "VLC Error", 
                                       "Could not launch VLC. Please make sure VLC Media Player is installed.")