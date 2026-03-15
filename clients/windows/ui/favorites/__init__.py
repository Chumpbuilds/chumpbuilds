"""Favorites module for IPTV Player"""

from .favorites_manager import FavoritesManager, get_favorites_manager
from .favorites_view import FavoritesView

__all__ = ['FavoritesManager', 'get_favorites_manager', 'FavoritesView']