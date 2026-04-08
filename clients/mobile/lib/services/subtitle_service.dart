import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

/// Singleton service for subtitle language preferences and API interaction.
///
/// Stores and retrieves preferred subtitle languages via SharedPreferences
/// (`subtitle_languages` key, defaults to `['en']`). The subtitle API is at
/// `https://x87player.xyz/subtitles`.
class SubtitleService {
  SubtitleService._();
  static final SubtitleService instance = SubtitleService._();

  static const String _baseUrl = 'https://x87player.xyz/subtitles';
  static const String _prefsKey = 'subtitle_languages';

  /// Returns the base URL for the subtitle API.
  static String get baseUrl => _baseUrl;

  /// Map of IETF language codes to display names.
  static const Map<String, String> availableLanguages = {
    'en': 'English',
    'fr': 'French',
    'de': 'German',
    'es': 'Spanish',
    'it': 'Italian',
    'pt': 'Portuguese',
    'nl': 'Dutch',
    'pl': 'Polish',
    'ru': 'Russian',
    'ar': 'Arabic',
    'tr': 'Turkish',
    'ro': 'Romanian',
    'el': 'Greek',
    'hu': 'Hungarian',
    'cs': 'Czech',
    'sv': 'Swedish',
    'da': 'Danish',
    'no': 'Norwegian',
    'fi': 'Finnish',
    'hr': 'Croatian',
    'bg': 'Bulgarian',
    'he': 'Hebrew',
    'zh': 'Chinese',
    'ja': 'Japanese',
    'ko': 'Korean',
    'th': 'Thai',
    'vi': 'Vietnamese',
    'id': 'Indonesian',
    'ms': 'Malay',
  };

  /// Returns the user's preferred subtitle languages from SharedPreferences.
  /// Defaults to `['en']` if not set.
  Future<List<String>> getPreferredLanguages() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_prefsKey);
    if (raw == null) return ['en'];
    try {
      final list = (jsonDecode(raw) as List<dynamic>).cast<String>();
      return list.isEmpty ? ['en'] : list;
    } catch (_) {
      return ['en'];
    }
  }

  /// Saves the user's preferred subtitle languages to SharedPreferences.
  Future<void> setPreferredLanguages(List<String> langs) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_prefsKey, jsonEncode(langs));
  }
}
