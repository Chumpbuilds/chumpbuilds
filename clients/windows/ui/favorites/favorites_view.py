"""
Favorites View - 4-column layout with Channels, Series, Movies, and Info
Fixed import issue
Current Date and Time (UTC): 2025-01-15 19:14:26
Current User: covchump
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                            QListWidgetItem, QLabel, QPushButton, QFrame,
                            QSplitter, QTextEdit, QMessageBox, QMenu)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QPoint
from PyQt6.QtGui import QFont, QPixmap, QAction, QCursor
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from player.vlc_player import get_vlc_player
from .favorites_manager import get_favorites_manager

class FavoritesList(QFrame):
    """Custom list widget for favorites"""
    item_selected = pyqtSignal(dict)
    item_removed = pyqtSignal(str)
    play_requested = pyqtSignal(dict)
    
    def __init__(self, title, icon, category, accent_color):
        super().__init__()
        self.title = title
        self.icon = icon
        self.category = category
        self.accent_color = accent_color
        self.favorites_manager = get_favorites_manager()
        self.init_ui()
    
    def init_ui(self):
        self.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Header
        header_layout = QHBoxLayout()
        
        icon_label = QLabel(self.icon)
        icon_label.setStyleSheet(f"font-size: 20px; color: {self.accent_color};")
        
        title_label = QLabel(self.title)
        title_label.setStyleSheet(f"""
            color: {self.accent_color};
            font-size: 16px;
            font-weight: bold;
        """)
        
        self.count_label = QLabel("0")
        self.count_label.setStyleSheet(f"""
            color: white;
            background: {self.accent_color};
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 12px;
            font-weight: bold;
        """)
        
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.count_label)
        
        layout.addLayout(header_layout)
        
        # List widget
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                color: white;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 5px;
                margin: 2px 0;
            }
            QListWidget::item:selected {
                background-color: rgba(255, 255, 255, 0.1);
            }
            QListWidget::item:hover {
                background-color: rgba(255, 255, 255, 0.05);
            }
        """)
        
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        
        layout.addWidget(self.list_widget)
        
        # Refresh favorites on init
        self.refresh_list()
    
    def refresh_list(self):
        """Refresh the favorites list"""
        self.list_widget.clear()
        favorites = self.favorites_manager.get_favorites(self.category)
        
        for fav in favorites:
            name = fav.get('name', 'Unknown')
            item = QListWidgetItem(f"{self.icon} {name}")
            item.setData(Qt.ItemDataRole.UserRole, fav)
            self.list_widget.addItem(item)
        
        self.count_label.setText(str(len(favorites)))
    
    def on_item_clicked(self, item):
        """Handle item selection"""
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            self.item_selected.emit(data)
    
    def on_item_double_clicked(self, item):
        """Handle double click to play"""
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            self.play_requested.emit(data)
    
    def show_context_menu(self, position: QPoint):
        """Show context menu for item"""
        item = self.list_widget.itemAt(position)
        if not item:
            return
        
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2c3e50;
                border: 1px solid #34495e;
                border-radius: 5px;
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
        play_action = QAction("▶ Play", self)
        play_action.triggered.connect(lambda: self.play_requested.emit(data))
        menu.addAction(play_action)
        
        # Remove from favorites
        remove_action = QAction("❌ Remove from Favorites", self)
        remove_action.triggered.connect(lambda: self.remove_item(data))
        menu.addAction(remove_action)
        
        menu.exec(QCursor.pos())
    
    def remove_item(self, data):
        """Remove item from favorites"""
        item_id = data.get('stream_id') or data.get('series_id')
        if item_id:
            if self.favorites_manager.remove_favorite(self.category, item_id):
                self.refresh_list()
                self.item_removed.emit(str(item_id))

class FavoritesView(QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.player = get_vlc_player()
        self.network_manager = QNetworkAccessManager()
        self.current_item = None
        self.init_ui()
    
    def init_ui(self):
        # Main layout
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create splitter for columns
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Channels column
        self.channels_list = FavoritesList(
            "Channels", "📺", "channels", "#3498db"
        )
        self.channels_list.item_selected.connect(self.on_channel_selected)
        self.channels_list.play_requested.connect(self.play_channel)
        splitter.addWidget(self.channels_list)
        
        # Series column
        self.series_list = FavoritesList(
            "Series", "📼", "series", "#9b59b6"
        )
        self.series_list.item_selected.connect(self.on_series_selected)
        self.series_list.play_requested.connect(self.play_series)
        splitter.addWidget(self.series_list)
        
        # Movies column
        self.movies_list = FavoritesList(
            "Movies", "🎬", "movies", "#e74c3c"
        )
        self.movies_list.item_selected.connect(self.on_movie_selected)
        self.movies_list.play_requested.connect(self.play_movie)
        splitter.addWidget(self.movies_list)
        
        # Info column
        self.create_info_column()
        splitter.addWidget(self.info_widget)
        
        # Set column widths (20%, 20%, 20%, 40%)
        splitter.setSizes([250, 250, 250, 500])
        
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
    
    def create_info_column(self):
        """Create the info/details column"""
        self.info_widget = QWidget()
        self.info_widget.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                border-left: 1px solid #3a3a3a;
            }
        """)
        
        layout = QVBoxLayout(self.info_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("Details")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #ffffff; padding: 5px;")
        layout.addWidget(title)
        
        # Poster/Logo
        self.info_poster = QLabel()
        self.info_poster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_poster.setFixedSize(200, 300)
        self.info_poster.setStyleSheet("""
            QLabel {
                background-color: #2c3e50;
                border-radius: 10px;
            }
        """)
        self.info_poster.setText("🎬")
        self.info_poster.setScaledContents(True)
        poster_font = QFont()
        poster_font.setPointSize(48)
        self.info_poster.setFont(poster_font)
        layout.addWidget(self.info_poster, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Item name
        self.info_name = QLabel("Select an item to view details")
        name_font = QFont()
        name_font.setPointSize(14)
        name_font.setBold(True)
        self.info_name.setFont(name_font)
        self.info_name.setStyleSheet("color: white; margin-top: 10px;")
        self.info_name.setWordWrap(True)
        self.info_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_name)
        
        # Info text
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setStyleSheet("""
            QTextEdit {
                background-color: #2c3e50;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.info_text)
        
        # Play button
        self.play_button = QPushButton("▶ Play")
        self.play_button.setEnabled(False)
        self.play_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 12px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.play_button.clicked.connect(self.play_current_item)
        layout.addWidget(self.play_button)
        
        # Remove button
        self.remove_button = QPushButton("❌ Remove from Favorites")
        self.remove_button.setEnabled(False)
        self.remove_button.setStyleSheet("""
            QPushButton {
                background-color: #c0392b;
                color: white;
                border: none;
                padding: 12px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #a93226;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.remove_button.clicked.connect(self.remove_current_item)
        layout.addWidget(self.remove_button)
        
        layout.addStretch()
    
    def on_channel_selected(self, channel_data):
        """Handle channel selection"""
        self.current_item = ('channel', channel_data)
        self.update_info_display(channel_data, 'channel')
    
    def on_series_selected(self, series_data):
        """Handle series selection"""
        self.current_item = ('series', series_data)
        self.update_info_display(series_data, 'series')
    
    def on_movie_selected(self, movie_data):
        """Handle movie selection"""
        self.current_item = ('movie', movie_data)
        self.update_info_display(movie_data, 'movie')
    
    def update_info_display(self, data, item_type):
        """Update the info display"""
        name = data.get('name', 'Unknown')
        self.info_name.setText(name)
        
        # Build info text
        info_parts = []
        
        if item_type == 'channel':
            info_parts.append(f"📺 Live Channel")
            if data.get('stream_id'):
                info_parts.append(f"ID: {data.get('stream_id')}")
        elif item_type == 'series':
            info_parts.append(f"📼 TV Series")
            if data.get('series_id'):
                info_parts.append(f"ID: {data.get('series_id')}")
            if data.get('year'):
                info_parts.append(f"Year: {data.get('year')}")
            if data.get('rating'):
                info_parts.append(f"Rating: {data.get('rating')}")
        elif item_type == 'movie':
            info_parts.append(f"🎬 Movie")
            if data.get('stream_id'):
                info_parts.append(f"ID: {data.get('stream_id')}")
            if data.get('year'):
                info_parts.append(f"Year: {data.get('year')}")
            if data.get('rating'):
                info_parts.append(f"Rating: {data.get('rating')}")
            if data.get('duration'):
                info_parts.append(f"Duration: {data.get('duration')}")
        
        # Add plot/description if available
        plot = data.get('plot') or data.get('description') or ''
        if plot:
            info_parts.append(f"\nPlot:\n{plot}")
        
        self.info_text.setText('\n'.join(info_parts))
        
        # Load poster/logo if available
        poster_url = data.get('stream_icon') or data.get('cover')
        if poster_url:
            self.load_poster(poster_url)
        else:
            self.info_poster.setPixmap(QPixmap())
            if item_type == 'channel':
                self.info_poster.setText("📺")
            elif item_type == 'series':
                self.info_poster.setText("📼")
            else:
                self.info_poster.setText("🎬")
        
        # Enable buttons
        self.play_button.setEnabled(True)
        self.remove_button.setEnabled(True)
    
    def load_poster(self, url):
        """Load poster image"""
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
                scaled_pixmap = pixmap.scaled(200, 300, Qt.AspectRatioMode.KeepAspectRatio, 
                                             Qt.TransformationMode.SmoothTransformation)
                self.info_poster.setPixmap(scaled_pixmap)
        reply.deleteLater()
    
    def play_current_item(self):
        """Play the currently selected item"""
        if not self.current_item:
            return
        
        item_type, data = self.current_item
        
        if item_type == 'channel':
            self.play_channel(data)
        elif item_type == 'series':
            self.play_series(data)
        elif item_type == 'movie':
            self.play_movie(data)
    
    def play_channel(self, channel_data):
        """Play a channel"""
        stream_id = channel_data.get('stream_id')
        if stream_id:
            stream_url = self.api.get_stream_url(stream_id, 'live')
            name = channel_data.get('name', 'Unknown')
            if self.player.play_stream(stream_url, name, True, 'live'):
                print(f"▶ Playing channel: {name}")
    
    def play_series(self, series_data):
        """Play a series (show episode selection)"""
        series_id = series_data.get('series_id')
        name = series_data.get('name', 'Unknown')
        
        if series_id:
            # Import here to avoid circular import at module level
            from ..dialogs.episode_selection import EpisodeSelectionDialog
            
            dialog = EpisodeSelectionDialog(name, series_id, self.api, self)
            dialog.exec()
    
    def play_movie(self, movie_data):
        """Play a movie"""
        stream_id = movie_data.get('stream_id')
        if stream_id:
            stream_url = self.api.get_stream_url(stream_id, 'movie', stream_data=movie_data)
            name = movie_data.get('name', 'Unknown')
            if self.player.play_stream(stream_url, name, True, 'movie'):
                print(f"▶ Playing movie: {name}")
    
    def remove_current_item(self):
        """Remove current item from favorites"""
        if not self.current_item:
            return
        
        item_type, data = self.current_item
        
        reply = QMessageBox.question(
            self,
            "Remove from Favorites",
            f"Remove '{data.get('name', 'Unknown')}' from favorites?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            favorites_manager = get_favorites_manager()
            item_id = data.get('stream_id') or data.get('series_id')
            
            if item_type == 'channel':
                category = 'channels'
            elif item_type == 'series':
                category = 'series'
            else:
                category = 'movies'
            
            if favorites_manager.remove_favorite(category, item_id):
                # Refresh the appropriate list
                if category == 'channels':
                    self.channels_list.refresh_list()
                elif category == 'series':
                    self.series_list.refresh_list()
                else:
                    self.movies_list.refresh_list()
                
                # Clear info display
                self.info_name.setText("Select an item to view details")
                self.info_text.clear()
                self.info_poster.setPixmap(QPixmap())
                self.info_poster.setText("🎬")
                self.play_button.setEnabled(False)
                self.remove_button.setEnabled(False)
                self.current_item = None
    
    def refresh_all(self):
        """Refresh all favorites lists"""
        self.channels_list.refresh_list()
        self.series_list.refresh_list()
        self.movies_list.refresh_list()