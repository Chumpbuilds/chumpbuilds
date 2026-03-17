# Mobile Build Guide (Android & iOS)

The X87 mobile client is a single Flutter project that builds for both Android and iOS from one codebase, located at `clients/mobile/`.

## Prerequisites

| Tool | Required for | Notes |
|------|-------------|-------|
| **Flutter SDK 3.41+** | Both platforms | [flutter.dev/docs/get-started/install](https://flutter.dev/docs/get-started/install) |
| **Android Studio** | Android | Includes Android SDK, emulator, build tools |
| **Xcode** | iOS only | macOS only — App Store install |

## Getting Started

```bash
cd clients/mobile
flutter pub get
```

## Running in Debug Mode

```bash
flutter run
```

Flutter will detect connected devices and emulators automatically. Use `flutter devices` to list available targets.

## Building for Release

### Android APK

```bash
flutter build apk --release
```

Output: `clients/mobile/build/app/outputs/flutter-apk/app-release.apk`

### iOS (requires macOS + Xcode)

```bash
flutter build ios --release
```

> ⚠️ iOS builds require macOS with Xcode installed. You will also need an Apple Developer account to sign and distribute the app.

## Project Structure

```
clients/mobile/
├── lib/          # Dart source code (main.dart entry point)
├── android/      # Android-specific configuration (Kotlin)
├── ios/          # iOS-specific configuration (Swift)
├── test/         # Widget and unit tests
└── pubspec.yaml  # Flutter project manifest and dependencies
```

## Backend API

The app connects to the X87 backend at **x87player.xyz**.

| Service | URL |
|---------|-----|
| Home / Landing | x87player.xyz |
| Customer Portal | portal.x87player.xyz |
| Admin Panel | admin.x87player.xyz |

