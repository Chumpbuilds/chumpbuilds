import Flutter
import UIKit

/// Factory that creates [IosPlayerPlatformView] instances for the Flutter
/// PlatformView registry.
///
/// Registered under the view type `com.x87player/ios_player_view` in
/// [AppDelegate]. Mirrors [ExoPlayerPlatformViewFactory] on Android.
class IosPlayerPlatformViewFactory: NSObject, FlutterPlatformViewFactory {

    private let messenger: FlutterBinaryMessenger

    init(messenger: FlutterBinaryMessenger) {
        self.messenger = messenger
        super.init()
    }

    func create(
        withFrame frame: CGRect,
        viewIdentifier viewId: Int64,
        arguments args: Any?
    ) -> FlutterPlatformView {
        return IosPlayerPlatformView(
            frame: frame,
            viewId: viewId,
            messenger: messenger,
            args: args as? [String: Any]
        )
    }

    func createArgsCodec() -> FlutterMessageCodec & NSObjectProtocol {
        return FlutterStandardMessageCodec.sharedInstance()
    }
}
