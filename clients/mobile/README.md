# X87 Mobile Client

Shared Flutter mobile client for **X87 Player** — builds for both **Android** and **iOS** from a single codebase.

## Video Player Architecture

The app uses a **hybrid native player architecture** — Flutter handles all UI (menus, EPG, login, settings, channel lists) while video playback is delegated to **native platform players** via platform channels and PlatformViews.

### Why native players?

The app went through multiple Flutter video player libraries (`flutter_vlc_player` → `media_kit` → `better_player_plus`) but none performed well on low-end Android TV hardware. The fundamental problem is that Flutter's texture-based video rendering copies every decoded frame through Flutter's compositor — an extra memory copy that kills performance on Amlogic SoCs.

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

| Device | Tunneling | Audio offload | Extension renderer mode |
|--------|-----------|---------------|------------------------|
| **Phones** | ✅ Enabled | ✅ Enabled | `MODE_ON` (hardware first, extension fallback) |
| **Fire Stick / Amlogic / Android TV** | ❌ Disabled | ❌ Disabled | `MODE_PREFER` (FFmpeg extension preferred) |

Audio tunneling and offload are disabled on TV devices because many **advertise support but don't implement it correctly**, causing silent playback — the root cause of the most common IPTV audio bugs on Amlogic boxes.

On TV/Amlogic devices `EXTENSION_RENDERER_MODE_PREFER` is used so that the FFmpeg software decoder is tried **before** hardware decoders. This is essential for DTS — Amlogic boxes have no native DTS hardware decoder, so hardware-first would silently fail.

### FFmpeg Decoder Extension (DTS / TrueHD support)

The app ships a custom-built **AndroidX Media FFmpeg decoder extension** AAR to handle audio codecs that Amlogic boxes cannot decode natively:

| Codec | MIME type | Native Amlogic decoder | FFmpeg extension |
|-------|-----------|----------------------|-----------------|
| DTS | `audio/vnd.dts` | ❌ None | ✅ `dca` |
| DTS-HD | `audio/vnd.dts.hd` | ❌ None | ✅ `dca` |
| TrueHD | `audio/true-hd` | ❌ None | ✅ `truehd` |
| AC3 / EAC3 | `audio/ac3`, `audio/eac3` | ✅ Amlogic OMX | ✅ Fallback |
| AAC / MP3 | standard | ✅ Hardware | ✅ Fallback |

#### Rebuilding the FFmpeg AAR

The pre-built AAR lives at `android/app/libs/lib-decoder-ffmpeg-release.aar`. If you need to rebuild it (e.g. to change enabled codecs or update the NDK):

**Source:** Clone the AndroidX Media repo and build the `lib-decoder-ffmpeg` module.

**NDK compatibility patch (required for NDK 26+):**

NDK 26 removed `stdout`/`stderr` as linkable symbols from the Android sysroot. The FFmpeg source's `libavutil/log.c` uses multi-line `fprintf(stdout, ...)` calls inside `ansi_fputs()` that must be replaced:

```bash
# Replace the entire ansi_fputs() body with a simple android log call
python3 << 'EOF'
with open('libavutil/log.c', 'r') as f:
    lines = f.readlines()

# Replace the function body (lines vary by FFmpeg version — adjust as needed)
# Find: static void ansi_fputs(...) { ... }
# Replace body with single __android_log_print call
new_body = [
    '{\n',
    '    __android_log_print(ANDROID_LOG_INFO, "ffmpeg", "%s", str);\n',
    '}\n'
]
# Replace lines between the opening { and closing } of ansi_fputs
# (check line numbers with: grep -n "static void ansi_fputs\|^}" libavutil/log.c)
lines[187:208] = new_body

with open('libavutil/log.c', 'w') as f:
    f.writelines(lines)
EOF

# Verify
grep -n "stdout\|stderr" libavutil/log.c   # should return nothing
```

Also replace any remaining single-line `fputs(str, stderr)` calls:
```bash
sed -i 's/fputs(str, stderr);/__android_log_print(ANDROID_LOG_INFO, "ffmpeg", "%s", str);/g' libavutil/log.c
```

**Build command:**
```bash
./build_ffmpeg.sh \
  ~/media/libraries/decoder_ffmpeg/src/main \
  ~/android-sdk/ndk/26.3.11579264 \
  linux-x86_64 \
  24 \
  aac ac3 eac3 dca mp3 vorbis flac truehd mlp
```

**`build.gradle` for the decoder module** must include `ndkVersion "26.3.11579264"` explicitly, otherwise Gradle falls back to a cached NDK 25 version.

After a successful build, copy the AAR:
```bash
cp buildout/outputs/aar/lib-decoder-ffmpeg-release.aar \
   clients/mobile/android/app/libs/lib-decoder-ffmpeg-release.aar
```

#### AmlogicAudioCodecSelector

`AmlogicAudioCodecSelector.kt` is a custom `MediaCodecSelector` that intercepts codec lookups for AC3, EAC3, and DTS MIME types. Many Amlogic boxes have working hardware decoders (e.g. `OMX.amlogic.ac3.decoder.awesome`) that are hidden from `MediaCodecList.REGULAR_CODECS` because they fail Android's standard compatibility tests. The selector uses `MediaCodecList.ALL_CODECS` to find them.

For DTS, since no Amlogic hardware decoder exists, the selector falls through to the FFmpeg extension renderer (via `EXTENSION_RENDERER_MODE_PREFER`).

### Key native files (Android)

```
android/app/src/main/kotlin/com/x87player/x87_mobile/
├── ExoPlayerFactory.kt              # Shared ExoPlayer builder (device detection, renderers, track selector, HTTP config)
├── AmlogicAudioCodecSelector.kt     # Custom codec selector — finds hidden Amlogic AC3/EAC3 decoders + DTS intercept
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
| **v4 (current)** | **Native ExoPlayer (Media3) + FFmpeg extension** | Zero-copy SurfaceView, DTS/TrueHD support, device-aware config |

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
│       ├── libs/              # Local AARs — FFmpeg decoder extension
│       └── build.gradle.kts   # Media3 ExoPlayer + local AAR dependencies
├── ios/                       # iOS-specific configuration + native Swift player
├── test/                      # Widget and unit tests
└── pubspec.yaml               # Flutter project manifest (no video player dependencies!)
```

> **Note:** `pubspec.yaml` has **zero video player dependencies**. All video rendering is handled natively via platform channels and PlatformViews, using Media3 ExoPlayer (declared in `build.gradle.kts`) and the FFmpeg decoder extension AAR in `android/app/libs/`.

## Backend

This app connects to the X87 backend API at **x87player.xyz**.

See [docs/mobile-build.md](../../docs/mobile-build.md) for full build instructions.
