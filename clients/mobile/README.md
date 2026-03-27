# X87 Mobile Client

Shared Flutter mobile client for **X87 Player** — builds for both **Android** and **iOS** from a single codebase.

## Video Player Architecture

The app uses a **hybrid native player architecture** — Flutter handles all UI (menus, EPG, login, settings, channel lists) while video playback is delegated to **native platform players** via platform channels and PlatformViews.

### Why native players?

The app went through multiple Flutter video player libraries (`flutter_vlc_player` → `media_kit` → `better_player_plus`) but none performed well on low-end Android TV hardware. The fundamental problem: **Flutter's texture bridge copies every video frame through its rendering pipeline**, adding overhead that kills performance on Fire Stick and Amlogic TV boxes.

Native Android apps like XCIPTV use ExoPlayer + SurfaceView, which renders video through Android's **zero-copy hardware compositor path** — no frame copying. That's why they're smooth. We now use the same approach.

### Two playback paths

The app provides two coexisting playback modes:

| Mode | How it works | Use case |
|------|-------------|----------|
| **Embedded** (inline) | `VlcPlayerWidget` → `AndroidView` → native `ExoPlayerPlatformView` → ExoPlayer + SurfaceView | Inline 16:9 video preview in channel lists, Movies, Series screens |
| **Fullscreen** | `AndroidHlsFullscreenScreen` → platform channel → `NativePlayerActivity` → ExoPlayer + SurfaceView | Dedicated fullscreen playback with D-pad/remote controls |

Both paths use the same underlying ExoPlayer configuration via `ExoPlayerFactory.kt` — shared device detection, renderer setup, and HTTP data source config.

### Device-aware configuration

The ExoPlayer setup automatically detects the device type at runtime:

| Device | Tunneling | Audio offload | Decoder fallback |
|--------|-----------|---------------|------------------|
| **Phones** | ✅ Enabled | ✅ Enabled | ✅ Enabled |
| **Fire Stick / Amlogic / Android TV** | ❌ Disabled | ❌ Disabled | ✅ Enabled |

Audio tunneling and offload are disabled on TV devices because many **advertise support but don't implement it correctly**, causing silent playback — the root cause of the most common IPTV audio bug on cheap Android TV boxes.

### Key native files (Android)

```
android/app/src/main/kotlin/com/x87player/x87_mobile/
├── ExoPlayerFactory.kt              # Shared ExoPlayer builder (device detection, renderers, track selector, HTTP config)
├── ExoPlayerPlatformView.kt         # PlatformView — ExoPlayer + PlayerView for embedded inline playback
├── ExoPlayerPlatformViewFactory.kt  # Factory registered with Flutter's platform view registry
├── MainActivity.kt                  # Flutter activity + platform channel for fullscreen + PlatformView registration
└── NativePlayerActivity.kt          # Standalone fullscreen Activity (ExoPlayer + SurfaceView + D-pad controls)
```

### Key Dart files

```
lib/
├── widgets/
│   ├── embedded_exo_player_widget.dart  # AndroidView wrapper for native ExoPlayer PlatformView
│   └── vlc_player_widget.dart           # Embedded video area — renders ExoPlayer on Android, placeholder on iOS
├── services/
│   └── video_player_service.dart        # Singleton — manages fullscreen playback via platform channel
└── screens/
    └── android_hls_fullscreen_screen.dart  # Thin launcher — calls NativePlayerActivity, pops on return
```

### iOS

iOS uses `AVPlayerViewController` presented modally via a platform channel in `AppDelegate.swift`. The embedded PlatformView path is Android-only; iOS falls back to the fullscreen-only flow.

### Player library timeline

| Version | Library | Outcome |
|---------|---------|---------|
| v1 | `flutter_vlc_player` | Black screen on Android 12+, hybrid composition issues |
| v2 | `media_kit` | Better but still frame-copying overhead on TV hardware |
| v3 | `better_player_plus` | Worked on phones, laggy + silent audio on Fire Stick/Amlogic |
| **v4 (current)** | **Native ExoPlayer (Media3)** | Zero-copy SurfaceView, device-aware config, works everywhere |

## Prerequisites

- **Flutter SDK** 3.7+
- **Android Studio** (for Android builds and emulator)
- **Xcode** (for iOS/macOS builds — macOS only)

## Getting Started

```bash
cd clients/mobile
flutter pub get
```

## Running in Debug Mode

```bash
flutter run
```

## Building

### Android APK
```bash
flutter build apk
```

### iOS (requires macOS + Xcode)
```bash
flutter build ios
```

## Project Structure

```
clients/mobile/
├── lib/
│   ├── main.dart              # App entry point, auto-login, theme
│   ├── screens/               # All screens (Home, Live TV, Movies, Series, Login, License, etc.)
│   ├── services/              # Business logic (Xtream API, license, video player, favourites, etc.)
│   └── widgets/               # Reusable widgets (player, focus items, TV text fields, etc.)
├── android/
│   └── app/
│       ├── src/main/kotlin/   # Native Kotlin code (ExoPlayer, PlatformView, Activities)
│       ├── src/main/AndroidManifest.xml
│       └── build.gradle.kts   # Media3 ExoPlayer dependencies
├── ios/                       # iOS-specific configuration + native Swift player
├── test/                      # Widget and unit tests
└── pubspec.yaml               # Flutter project manifest (no video player dependencies!)
```

> **Note:** `pubspec.yaml` has **zero video player dependencies**. All video rendering is handled natively via platform channels and PlatformViews, using Media3 ExoPlayer (declared in `build.gradle.kts`).

## Backend

This app connects to the X87 backend API at **x87player.xyz**.

See [docs/mobile-build.md](../../docs/mobile-build.md) for full build instructions.
