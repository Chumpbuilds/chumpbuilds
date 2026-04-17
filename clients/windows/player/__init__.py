"""Player module for IPTV Player"""

from .mpv_player import EmbeddedMPVPlayer, get_embedded_mpv_player
from .vlc_player import ExternalVLCPlayer, get_embedded_vlc_player, get_vlc_player

__all__ = [
    "EmbeddedMPVPlayer",
    "ExternalVLCPlayer",
    "get_embedded_mpv_player",
    "get_embedded_vlc_player",
    "get_vlc_player",
]
