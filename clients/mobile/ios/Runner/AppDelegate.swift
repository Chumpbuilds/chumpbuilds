import UIKit
import Flutter

@main
@objc class AppDelegate: FlutterAppDelegate {
    override func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
    ) -> Bool {
        GeneratedPluginRegistrant.register(with: self)
        // Call super first so that Flutter's window and rootViewController are created.
        let launched = super.application(application, didFinishLaunchingWithOptions: launchOptions)
        registerNativePlayerChannel()
        registerIosPlayerPlatformView()
        return launched
    }

    // MARK: - Native player platform channel

    private func registerNativePlayerChannel() {
        guard let flutterVC = window?.rootViewController as? FlutterViewController else { return }

        let channel = FlutterMethodChannel(
            name: "com.x87player/native_player",
            binaryMessenger: flutterVC.binaryMessenger
        )

        channel.setMethodCallHandler { [weak flutterVC] call, result in
            guard call.method == "launchPlayer" else {
                result(FlutterMethodNotImplemented)
                return
            }
            guard
                let args = call.arguments as? [String: Any],
                let urlString = args["url"] as? String,
                let url = URL(string: urlString),
                let presenter = flutterVC
            else {
                result(FlutterError(code: "INVALID_ARGS", message: "url is required", details: nil))
                return
            }

            let title = args["title"] as? String
            let contentType = args["contentType"] as? String ?? "live"

            if contentType == "movie" || contentType == "series" {
                let vlcVC = VLCPlayerViewController()
                vlcVC.streamURL = url
                vlcVC.streamTitle = title
                vlcVC.modalPresentationStyle = .fullScreen
                vlcVC.onDismissed = {
                    result("dismissed")
                }
                presenter.present(vlcVC, animated: true, completion: nil)
            } else {
                let playerVC = NativePlayerViewController()
                playerVC.streamURL = url
                playerVC.streamTitle = title
                playerVC.modalPresentationStyle = .fullScreen
                playerVC.onDismissed = {
                    result("dismissed")
                }
                presenter.present(playerVC, animated: true, completion: nil)
            }
        }
    }

    // MARK: - iOS embedded player platform view

    private func registerIosPlayerPlatformView() {
        guard let flutterVC = window?.rootViewController as? FlutterViewController else { return }
        let factory = IosPlayerPlatformViewFactory(messenger: flutterVC.binaryMessenger)
        let registrar = flutterVC.registrar(forPlugin: "IosPlayerPlatformView")!
        registrar.register(factory, withId: "com.x87player/ios_player_view")
    }
}

