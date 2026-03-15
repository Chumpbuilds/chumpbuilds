"""
Modern Global Search - Smart 3-Column Layout: Live TV | Movies | Series
Clean list format with episode selection for series
Added Favorites functionality from search results and Clear Search button
Current Date and Time (UTC): 2025-11-16 08:53:19
Current User: covchump
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QLineEdit, QProgressBar, QMessageBox,
                            QScrollArea, QFrame, QListWidget, QListWidgetItem,
                            QDialog, QTreeWidget, QTreeWidgetItem, QDialogButtonBox, QMenu)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QPoint
from PyQt6.QtGui import QFont, QCursor, QAction
from player.vlc_player import get_vlc_player
from ui.dialogs.episode_selection import EpisodeSelectionDialog

# Add favorites import
try:
    from .favorites.favorites_manager import get_favorites_manager
except (ImportError, ModuleNotFoundError):
    # Fallback if favorites module doesn't exist yet
    def get_favorites_manager():
        print("[Search] Favorites Manager not found.")
        return None

# Separate threads for parallel loading
class ChannelsLoaderThread(QThread):
    loaded = pyqtSignal(list)
    
    def __init__(self, api):
        super().__init__()
        self.api = api
    
    def run(self):
        try:
            channels = self.api.get_live_streams(None)
            # Filter out None values and ensure we have a list
            if channels:
                channels = [ch for ch in channels if ch is not None]
            self.loaded.emit(channels if channels else [])
        except Exception as e:
            print(f"Error loading channels: {e}")
            self.loaded.emit([])

class MoviesLoaderThread(QThread):
    loaded = pyqtSignal(list)
    
    def __init__(self, api):
        super().__init__()
        self.api = api
    
    def run(self):
        try:
            movies = self.api.get_vod_streams(None)
            # Filter out None values and ensure we have a list
            if movies:
                movies = [m for m in movies if m is not None]
            self.loaded.emit(movies if movies else [])
        except Exception as e:
            print(f"Error loading movies: {e}")
            self.loaded.emit([])

class SeriesLoaderThread(QThread):
    loaded = pyqtSignal(list)
    
    def __init__(self, api):
        super().__init__()
        self.api = api
    
    def run(self):
        try:
            series = self.api.get_series(None)
            # Filter out None values and ensure we have a list
            if series:
                series = [s for s in series if s is not None]
            self.loaded.emit(series if series else [])
        except Exception as e:
            print(f"Error loading series: {e}")
            self.loaded.emit([])

class SearchColumn(QFrame):
    """Column with clean list format and favorites functionality"""
    def __init__(self, title, icon, accent_color, api):
        super().__init__()
        self.title = title
        self.icon = icon
        self.accent_color = accent_color
        self.api = api
        
        # Initialize favorites manager
        self.favorites_manager = get_favorites_manager()
        
        self.init_ui()
    
    def init_ui(self):
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.05);
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(15)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)
        
        icon_label = QLabel(self.icon)
        icon_label.setStyleSheet(f"""
            QLabel {{
                color: {self.accent_color};
                font-size: 24px;
                background: transparent;
            }}
        """)
        
        title_label = QLabel(self.title)
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {self.accent_color};
                font-size: 16px;
                font-weight: 700;
                letter-spacing: 1px;
                background: transparent;
            }}
        """)
        
        self.count_label = QLabel("0")
        self.count_label.setStyleSheet(f"""
            QLabel {{
                color: {self.accent_color};
                font-size: 14px;
                font-weight: 600;
                background: rgba(255, 255, 255, 0.1);
                padding: 4px 10px;
                border-radius: 10px;
            }}
        """)
        
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.count_label)
        
        layout.addLayout(header_layout)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background-color: {self.accent_color}; max-height: 2px; border: none;")
        layout.addWidget(separator)
        
        # List widget for clean results
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                color: white;
                font-size: 14px;
                outline: none;
            }
            QListWidget::item {
                padding: 10px;
                border-radius: 6px;
                margin: 2px 0px;
            }
            QListWidget::item:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
            QListWidget::item:selected {
                background-color: rgba(255, 255, 255, 0.15);
                color: white;
            }
            QScrollBar:vertical {
                background-color: rgba(255, 255, 255, 0.1);
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(255, 255, 255, 0.3);
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: rgba(255, 255, 255, 0.5);
            }
        """)
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        
        # ADD CONTEXT MENU FOR FAVORITES
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        
        layout.addWidget(self.list_widget)
    
    def add_result(self, name, content_type, data):
        """Add a result to the list"""
        item = QListWidgetItem(name)
        item.setData(Qt.ItemDataRole.UserRole, {'type': content_type, 'data': data})
        self.list_widget.addItem(item)
        self.update_count()
    
    def on_item_double_clicked(self, item):
        """Handle item double-click"""
        item_data = item.data(Qt.ItemDataRole.UserRole)
        content_type = item_data['type']
        data = item_data['data']
        name = item.text()
        
        try:
            if content_type == "Live TV":
                stream_id = data.get('stream_id')
                if stream_id:
                    stream_url = self.api.get_stream_url(stream_id, 'live')
                    if stream_url:
                        player = get_vlc_player()
                        player.play_stream(stream_url, name, True, 'live')
                        
            elif content_type == "Movie":
                stream_id = data.get('stream_id')
                if stream_id:
                    stream_url = self.api.get_stream_url(stream_id, 'movie', stream_data=data)
                    if stream_url:
                        player = get_vlc_player()
                        player.play_stream(stream_url, name, True, 'movie')
                        
            elif content_type == "Series":
                series_id = data.get('series_id')
                if series_id:
                    dialog = EpisodeSelectionDialog(name, series_id, self.api, self.window())
                    dialog.exec()
                    
        except Exception as e:
            print(f"Error playing content: {e}")
            QMessageBox.critical(self.window(), "Error", f"Playback failed: {str(e)}")
    
    def show_context_menu(self, position: QPoint):
        """Show context menu for adding/removing favorites"""
        item = self.list_widget.itemAt(position)
        if not item:
            return
            
        item_data = item.data(Qt.ItemDataRole.UserRole)
        if not item_data:
            return
            
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #2c3e50; border: 1px solid #34495e; }
            QMenu::item { padding: 8px 20px; color: white; }
            QMenu::item:selected { background-color: #34495e; }
        """)
        
        # Play action
        play_action = QAction("▶ Play", self)
        play_action.triggered.connect(lambda: self.on_item_double_clicked(item))
        menu.addAction(play_action)
        
        if self.favorites_manager:
            menu.addSeparator()
            
            content_type = item_data['type']
            data = item_data['data']
            
            category = None
            item_id = None
            
            if content_type == "Live TV":
                category = "channels"
                item_id = data.get('stream_id')
            elif content_type == "Movie":
                category = "movies"
                item_id = data.get('stream_id')
            elif content_type == "Series":
                category = "series"
                item_id = data.get('series_id')
            
            if category and item_id:
                is_favorite = self.favorites_manager.is_favorite(category, str(item_id))
                
                if is_favorite:
                    remove_action = QAction("❌ Remove from Favorites", self)
                    remove_action.triggered.connect(lambda: self.remove_from_favorites(category, item_id, item))
                    menu.addAction(remove_action)
                else:
                    add_action = QAction("⭐ Add to Favorites", self)
                    add_action.triggered.connect(lambda: self.add_to_favorites(category, data, item))
                    menu.addAction(add_action)
                    
        menu.exec(QCursor.pos())

    def add_to_favorites(self, category, data, item):
        """Add item to favorites and update UI"""
        if self.favorites_manager.add_favorite(category, data):
            if self.window() and hasattr(self.window(), 'update_favorites_count'):
                self.window().update_favorites_count()
            # Update item text to show it's a favorite
            item.setText(f"⭐ {data.get('name', 'Unknown')}")
            QMessageBox.information(self, "Favorite Added", f"'{data.get('name')}' has been added to your favorites.")

    def remove_from_favorites(self, category, item_id, item):
        """Remove item from favorites and update UI"""
        if self.favorites_manager.remove_favorite(category, str(item_id)):
            if self.window() and hasattr(self.window(), 'update_favorites_count'):
                self.window().update_favorites_count()
            # Update item text to remove the star
            name = item.text().replace("⭐ ", "🔍 ")
            item.setText(name)
            QMessageBox.information(self, "Favorite Removed", f"Item has been removed from your favorites.")
    
    def clear_results(self):
        """Clear all results"""
        self.list_widget.clear()
        self.update_count()
    
    def update_count(self):
        """Update result count"""
        count = self.list_widget.count()
        self.count_label.setText(f"{count}")

class ModernGlobalSearch(QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.all_channels = []
        self.all_movies = []
        self.all_series = []
        
        self.channels_loaded = False
        self.movies_loaded = False
        self.series_loaded = False
        
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._execute_search)
        
        self.channels_thread = None
        self.movies_thread = None
        self.series_thread = None
        
        # Init favorites manager to ensure it's available
        self.favorites_manager = get_favorites_manager()
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # Header
        title = QLabel("Global Search")
        title_font = QFont()
        title_font.setPointSize(28)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #ffffff; background: transparent;")
        layout.addWidget(title)
        
        # Search input with clear button
        search_layout = QHBoxLayout()
        search_layout.setSpacing(10)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search across all content...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 15px 22px;
                font-size: 15px;
                border: 2px solid rgba(255, 255, 255, 0.2);
                border-radius: 24px;
                background-color: rgba(255, 255, 255, 0.1);
                color: #ffffff;
            }
            QLineEdit:focus {
                border: 2px solid #64b5f6;
                background-color: rgba(255, 255, 255, 0.15);
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.6);
            }
        """)
        self.search_input.setMinimumHeight(50)
        self.search_input.textChanged.connect(self.on_search_text_changed)
        
        # Clear search button
        self.clear_button = QPushButton("✕ Clear")
        self.clear_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ff6b6b,
                    stop:1 #ffa500);
                color: white;
                border: none;
                border-radius: 24px;
                padding: 15px 25px;
                font-size: 14px;
                font-weight: 600;
                min-height: 20px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ff5252,
                    stop:1 #ff9800);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #e53935,
                    stop:1 #f57c00);
            }
        """)
        self.clear_button.clicked.connect(self.clear_search)
        self.clear_button.hide()  # Initially hidden
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.clear_button)
        layout.addLayout(search_layout)
        
        # Status label only (no progress bar)
        self.status_label = QLabel("Loading content...")
        self.status_label.setStyleSheet("color: rgba(255, 255, 255, 0.9); font-size: 13px; font-weight: 500;")
        layout.addWidget(self.status_label)
        
        # 3-Column Layout
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(20)
        
        self.livetv_column = SearchColumn("LIVE TV", "📺", "#8b9cff", self.api)
        columns_layout.addWidget(self.livetv_column)
        
        self.movies_column = SearchColumn("MOVIES", "🎬", "#ff9eff", self.api)
        columns_layout.addWidget(self.movies_column)
        
        self.series_column = SearchColumn("SERIES", "📼", "#64d4ff", self.api)
        columns_layout.addWidget(self.series_column)
        
        layout.addLayout(columns_layout)
        
        self.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
        """)
    
    def clear_search(self):
        """Clear the search input and results"""
        self.search_input.clear()
        self.clear_all_results()
        self.clear_button.hide()
        print("[Search] Search cleared by user")
    
    def load_all_content(self):
        """Load all content from API"""
        if not self.api or not self.api.is_authenticated():
            self.status_label.setText("Error: Not authenticated")
            return
        
        self.status_label.setText("Loading channels, movies, and series...")
        
        self.channels_thread = ChannelsLoaderThread(self.api)
        self.channels_thread.loaded.connect(self.on_channels_loaded)
        self.channels_thread.start()
        
        self.movies_thread = MoviesLoaderThread(self.api)
        self.movies_thread.loaded.connect(self.on_movies_loaded)
        self.movies_thread.start()
        
        self.series_thread = SeriesLoaderThread(self.api)
        self.series_thread.loaded.connect(self.on_series_loaded)
        self.series_thread.start()
    
    def on_channels_loaded(self, channels):
        self.all_channels = channels or []
        self.channels_loaded = True
        self.update_status()
        print(f"✓ Loaded {len(self.all_channels)} channels")
    
    def on_movies_loaded(self, movies):
        self.all_movies = movies or []
        self.movies_loaded = True
        self.update_status()
        print(f"✓ Loaded {len(self.all_movies)} movies")
    
    def on_series_loaded(self, series):
        self.all_series = series or []
        self.series_loaded = True
        self.update_status()
        print(f"✓ Loaded {len(self.all_series)} series")
    
    def update_status(self):
        """Update loading status"""
        if self.channels_loaded and self.movies_loaded and self.series_loaded:
            total = len(self.all_channels) + len(self.all_movies) + len(self.all_series)
            self.status_label.setText(f"✓ Ready • 📺 {len(self.all_channels):,} • 🎬 {len(self.all_movies):,} • 📼 {len(self.all_series):,} ({total:,} total)")
            self.status_label.setStyleSheet("color: #4ade80; font-size: 13px; font-weight: 600;")
        else:
            parts = []
            if self.channels_loaded:
                parts.append(f"📺 {len(self.all_channels):,}")
            if self.movies_loaded:
                parts.append(f"🎬 {len(self.all_movies):,}")
            if self.series_loaded:
                parts.append(f"📼 {len(self.all_series):,}")
            self.status_label.setText(f"Loading: {' • '.join(parts)}...")
    
    def on_search_text_changed(self, text):
        """Debounce search and show/hide clear button"""
        self.search_timer.stop()
        if text.strip():
            self.search_timer.start(300)
            self.clear_button.show()  # Show clear button when there's text
        else:
            self.clear_all_results()
            self.clear_button.hide()  # Hide clear button when input is empty
    
    def _execute_search(self):
        """Execute search"""
        query = self.search_input.text()
        self.perform_search(query)
    
    def perform_search(self, query):
        """Search and populate columns"""
        if not query or not query.strip():
            self.clear_all_results()
            return
        
        query_lower = query.lower().strip()
        self.clear_all_results()
        
        max_per_column = 100
        
        # Search channels
        count = 0
        for channel in self.all_channels:
            if count >= max_per_column: break
            if isinstance(channel, dict):
                name = channel.get('name')
                if name is None: continue
                
                name_str = str(name)
                if query_lower in name_str.lower():
                    stream_id = channel.get('stream_id')
                    is_fav = self.favorites_manager and self.favorites_manager.is_favorite('channels', str(stream_id))
                    prefix = "⭐ " if is_fav else "🔍 "
                    self.livetv_column.add_result(f"{prefix}{name_str}", "Live TV", channel)
                    count += 1
        
        # Search movies
        count = 0
        for movie in self.all_movies:
            if count >= max_per_column: break
            if isinstance(movie, dict):
                name = movie.get('name')
                if name is None: continue
                
                name_str = str(name)
                if query_lower in name_str.lower():
                    stream_id = movie.get('stream_id')
                    is_fav = self.favorites_manager and self.favorites_manager.is_favorite('movies', str(stream_id))
                    prefix = "⭐ " if is_fav else "🔍 "
                    self.movies_column.add_result(f"{prefix}{name_str}", "Movie", movie)
                    count += 1
        
        # Search series
        count = 0
        for series in self.all_series:
            if count >= max_per_column: break
            if isinstance(series, dict):
                name = series.get('name')
                if name is None: continue
                
                name_str = str(name)
                if query_lower in name_str.lower():
                    series_id = series.get('series_id')
                    is_fav = self.favorites_manager and self.favorites_manager.is_favorite('series', str(series_id))
                    prefix = "⭐ " if is_fav else "🔍 "
                    self.series_column.add_result(f"{prefix}{name_str}", "Series", series)
                    count += 1
    
    def clear_all_results(self):
        """Clear all columns"""
        self.livetv_column.clear_results()
        self.movies_column.clear_results()
        self.series_column.clear_results()
    
    def closeEvent(self, event):
        """Clean up"""
        try:
            if hasattr(self, 'search_timer'):
                self.search_timer.stop()
            
            if self.channels_thread and self.channels_thread.isRunning():
                self.channels_thread.quit()
                self.channels_thread.wait(1000)
            if self.movies_thread and self.movies_thread.isRunning():
                self.movies_thread.quit()
                self.movies_thread.wait(1000)
            if self.series_thread and self.series_thread.isRunning():
                self.series_thread.quit()
                self.series_thread.wait(1000)
            
            event.accept()
        except Exception as e:
            print(f"Error during close: {e}")
            event.accept()