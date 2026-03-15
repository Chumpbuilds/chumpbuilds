"""
Favorites Manager - Handles saving and loading favorites
Current Date and Time (UTC): 2025-11-15 19:08:17
Current User: covchump
"""

import json
import os
from typing import Dict, List, Optional
from PyQt6.QtCore import QSettings

class FavoritesManager:
    """Manages favorites for channels, movies, and series"""
    
    def __init__(self):
        self.settings = QSettings('IPTVPlayer', 'Favorites')
        self.favorites_file = os.path.join(
            os.path.expanduser('~'), 
            '.iptv_cache', 
            'favorites.json'
        )
        
        # Ensure cache directory exists
        os.makedirs(os.path.dirname(self.favorites_file), exist_ok=True)
        
        # Load favorites
        self.favorites = self.load_favorites()
    
    def load_favorites(self) -> Dict:
        """Load favorites from file"""
        if os.path.exists(self.favorites_file):
            try:
                with open(self.favorites_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Ensure all categories exist
                    for category in ['channels', 'movies', 'series']:
                        if category not in data:
                            data[category] = []
                    return data
            except Exception as e:
                print(f"[Favorites] Error loading favorites: {e}")
        
        # Return empty structure
        return {
            'channels': [],
            'movies': [],
            'series': []
        }
    
    def save_favorites(self):
        """Save favorites to file"""
        try:
            with open(self.favorites_file, 'w', encoding='utf-8') as f:
                json.dump(self.favorites, f, indent=2)
            print(f"[Favorites] Saved {self.get_total_count()} favorites")
        except Exception as e:
            print(f"[Favorites] Error saving favorites: {e}")
    
    def add_favorite(self, category: str, item: Dict) -> bool:
        """Add item to favorites"""
        if category not in self.favorites:
            return False
        
        # Check if already exists (by stream_id or series_id)
        item_id = item.get('stream_id') or item.get('series_id')
        if not item_id:
            return False
        
        # Check for duplicates
        for fav in self.favorites[category]:
            fav_id = fav.get('stream_id') or fav.get('series_id')
            if fav_id == item_id:
                print(f"[Favorites] Item already in {category} favorites")
                return False
        
        # Add to favorites
        self.favorites[category].append(item)
        self.save_favorites()
        print(f"[Favorites] Added to {category}: {item.get('name', 'Unknown')}")
        return True
    
    def remove_favorite(self, category: str, item_id: str) -> bool:
        """Remove item from favorites"""
        if category not in self.favorites:
            return False
        
        # Find and remove item
        for i, fav in enumerate(self.favorites[category]):
            fav_id = str(fav.get('stream_id') or fav.get('series_id', ''))
            if fav_id == str(item_id):
                removed = self.favorites[category].pop(i)
                self.save_favorites()
                print(f"[Favorites] Removed from {category}: {removed.get('name', 'Unknown')}")
                return True
        
        return False
    
    def is_favorite(self, category: str, item_id: str) -> bool:
        """Check if item is in favorites"""
        if category not in self.favorites:
            return False
        
        for fav in self.favorites[category]:
            fav_id = str(fav.get('stream_id') or fav.get('series_id', ''))
            if fav_id == str(item_id):
                return True
        
        return False
    
    def get_favorites(self, category: str) -> List[Dict]:
        """Get favorites for a category"""
        return self.favorites.get(category, [])
    
    def get_all_favorites(self) -> Dict:
        """Get all favorites"""
        return self.favorites
    
    def clear_category(self, category: str):
        """Clear all favorites in a category"""
        if category in self.favorites:
            self.favorites[category] = []
            self.save_favorites()
            print(f"[Favorites] Cleared {category} favorites")
    
    def clear_all(self):
        """Clear all favorites"""
        self.favorites = {
            'channels': [],
            'movies': [],
            'series': []
        }
        self.save_favorites()
        print("[Favorites] Cleared all favorites")
    
    def get_total_count(self) -> int:
        """Get total number of favorites"""
        return sum(len(self.favorites[cat]) for cat in self.favorites)
    
    def get_category_count(self, category: str) -> int:
        """Get number of favorites in a category"""
        return len(self.favorites.get(category, []))

# Singleton instance
_favorites_manager = None

def get_favorites_manager():
    """Get or create favorites manager instance"""
    global _favorites_manager
    if _favorites_manager is None:
        _favorites_manager = FavoritesManager()
    return _favorites_manager