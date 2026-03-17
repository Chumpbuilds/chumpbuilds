# X87 Mobile Client

Shared Flutter mobile client for **X87 Player** — builds for both **Android** and **iOS** from a single codebase.

## Prerequisites

- **Flutter SDK** 3.41+
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
├── lib/          # Dart source code
├── android/      # Android-specific configuration
├── ios/          # iOS-specific configuration
├── test/         # Widget and unit tests
└── pubspec.yaml  # Flutter project manifest
```

## Backend

This app connects to the X87 backend API at **x87player.xyz**.

See [docs/mobile-build.md](../../docs/mobile-build.md) for full build instructions.
