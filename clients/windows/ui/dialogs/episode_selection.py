"""
Episode Selection Dialog - Separated to avoid circular imports
Current Date and Time (UTC): 2025-01-15 19:14:26
Current User: covchump
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QTreeWidget, QTreeWidgetItem, 
                            QProgressBar, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from player.vlc_player import get_vlc_player

class SeriesInfoThread(QThread):
    """Thread to load series episodes"""
    info_loaded = pyqtSignal(dict)
    
    def __init__(self, api, series_id):
        super().__init__()
        self.api = api
        self.series_id = series_id
    
    def run(self):
        try:
            info = self.api.get_series_info(self.series_id)
            self.info_loaded.emit(info if info else {})
        except Exception as e:
            print(f"Error loading series info: {e}")
            self.info_loaded.emit({})

class EpisodeSelectionDialog(QDialog):
    """Dialog to select and play series episodes"""
    def __init__(self, series_name, series_id, api, parent=None):
        super().__init__(parent)
        self.series_name = series_name
        self.series_id = series_id
        self.api = api
        self.player = get_vlc_player()
        self.series_data = None
        self.init_ui()
        self.load_episodes()
    
    def init_ui(self):
        self.setWindowTitle(f"Episodes - {self.series_name}")
        self.setMinimumSize(600, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
            QLabel {
                color: white;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)
        
        # Title
        title = QLabel(self.series_name)
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #64d4ff; padding: 10px;")
        layout.addWidget(title)
        
        # Loading label
        self.loading_label = QLabel("Loading episodes...")
        self.loading_label.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 13px;")
        layout.addWidget(self.loading_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 5px;
                background-color: rgba(255, 255, 255, 0.1);
                height: 8px;
            }
            QProgressBar::chunk {
                background-color: #64d4ff;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Episodes tree
        self.episodes_tree = QTreeWidget()
        self.episodes_tree.setHeaderLabel("Seasons & Episodes")
        self.episodes_tree.setStyleSheet("""
            QTreeWidget {
                background-color: rgba(255, 255, 255, 0.05);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 5px;
                font-size: 13px;
            }
            QTreeWidget::item {
                padding: 8px;
                border-radius: 4px;
            }
            QTreeWidget::item:selected {
                background-color: rgba(100, 212, 255, 0.3);
            }
            QTreeWidget::item:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
            QTreeWidget::branch {
                background-color: transparent;
            }
        """)
        self.episodes_tree.itemDoubleClicked.connect(self.play_episode)
        layout.addWidget(self.episodes_tree)
        
        # Info label
        info_label = QLabel("💡 Double-click an episode to play")
        info_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 12px; padding: 5px;")
        layout.addWidget(info_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.play_button = QPushButton("▶ Play Selected")
        self.play_button.setStyleSheet("""
            QPushButton {
                background-color: #64d4ff;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #50c0ff;
            }
            QPushButton:disabled {
                background-color: rgba(255, 255, 255, 0.2);
                color: rgba(255, 255, 255, 0.5);
            }
        """)
        self.play_button.clicked.connect(self.play_selected_episode)
        self.play_button.setEnabled(False)
        
        close_button = QPushButton("Close")
        close_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.2);
                padding: 10px 20px;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.15);
            }
        """)
        close_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.play_button)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
    
    def load_episodes(self):
        """Load series episodes in background"""
        self.info_thread = SeriesInfoThread(self.api, self.series_id)
        self.info_thread.info_loaded.connect(self.on_episodes_loaded)
        self.info_thread.start()
    
    def on_episodes_loaded(self, info):
        """Handle loaded episodes"""
        self.progress_bar.hide()
        self.loading_label.hide()
        
        if not info:
            self.loading_label.setText("❌ Failed to load episodes")
            self.loading_label.setStyleSheet("color: #ff6b6b; font-size: 13px;")
            self.loading_label.show()
            return
        
        self.series_data = info
        self.populate_episodes(info)
        self.play_button.setEnabled(True)
    
    def populate_episodes(self, info):
        """Populate the episode tree"""
        self.episodes_tree.clear()
        
        # Try different data structures
        episodes_data = None
        
        if 'episodes' in info:
            episodes_data = info['episodes']
        elif 'seasons' in info:
            episodes_data = info['seasons']
        
        if not episodes_data:
            no_episodes = QTreeWidgetItem(self.episodes_tree)
            no_episodes.setText(0, "No episodes found")
            return
        
        # Process episodes
        if isinstance(episodes_data, dict):
            self.process_episodes_dict(episodes_data)
        elif isinstance(episodes_data, list):
            self.process_episodes_list(episodes_data)
    
    def process_episodes_dict(self, episodes):
        """Process episodes in dictionary format"""
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
        """Process episodes in list format"""
        seasons = {}
        
        for episode_data in episodes:
            if isinstance(episode_data, dict):
                season_num = episode_data.get('season', 1)
                if season_num not in seasons:
                    seasons[season_num] = []
                seasons[season_num].append(episode_data)
        
        self.add_seasons_to_tree(seasons)
    
    def add_seasons_to_tree(self, seasons):
        """Add seasons and episodes to tree"""
        for season_num in sorted(seasons.keys()):
            season_item = QTreeWidgetItem(self.episodes_tree)
            season_item.setText(0, f"📁 Season {season_num}")
            season_item.setExpanded(True)
            
            # Sort episodes
            season_episodes = sorted(seasons[season_num], 
                                   key=lambda x: x.get('episode_num', 0) if isinstance(x, dict) else 0)
            
            for episode in season_episodes:
                if isinstance(episode, dict):
                    episode_item = QTreeWidgetItem(season_item)
                    episode_num = episode.get('episode_num', '?')
                    episode_title = episode.get('title', episode.get('name', 'Unknown'))
                    episode_item.setText(0, f"▶ Episode {episode_num}: {episode_title}")
                    episode_item.setData(0, Qt.ItemDataRole.UserRole, episode)
        
        self.loading_label.setText(f"✓ Loaded {self.episodes_tree.topLevelItemCount()} seasons")
        self.loading_label.setStyleSheet("color: #4ade80; font-size: 13px;")
        self.loading_label.show()
    
    def play_selected_episode(self):
        """Play the selected episode"""
        current_item = self.episodes_tree.currentItem()
        if current_item and current_item.parent():
            self.play_episode(current_item, 0)
    
    def play_episode(self, item, column):
        """Play the episode"""
        if not item.parent():
            return
        
        episode_data = item.data(0, Qt.ItemDataRole.UserRole)
        if not episode_data:
            return
        
        try:
            season_num = episode_data.get('season', episode_data.get('season_num', 1))
            episode_num = episode_data.get('episode_num', episode_data.get('episode', '?'))
            episode_title = episode_data.get('title', episode_data.get('name', 'Unknown Episode'))
            
            container_extension = (episode_data.get('container_extension') or 
                                 episode_data.get('extension') or 
                                 episode_data.get('ext') or 
                                 'mp4')
            
            episode_id = episode_data.get('id', episode_data.get('episode_id'))
            
            full_title = f"{self.series_name} - S{season_num:02d}E{episode_num:02d} - {episode_title}"
            
            if episode_id:
                stream_url = f"{self.api.base_url}/series/{self.api.username}/{self.api.password}/{episode_id}.{container_extension}"
            else:
                stream_url = f"{self.api.base_url}/series/{self.api.username}/{self.api.password}/{self.series_id}.{container_extension}"
            
            if self.player.play_stream(stream_url, full_title, True, 'series'):
                print(f"▶ Playing: {full_title}")
                self.accept()
            else:
                QMessageBox.critical(self, "Error", "Failed to launch VLC.")
                
        except Exception as e:
            print(f"Error playing episode: {e}")
            QMessageBox.critical(self, "Error", f"Failed to play episode: {str(e)}")