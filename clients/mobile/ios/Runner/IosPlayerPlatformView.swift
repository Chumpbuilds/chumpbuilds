import AVFoundation
import Flutter
import UIKit

/// Native iOS platform view that hosts an [AVPlayerLayer] directly.
///
/// This follows the same architecture as [ExoPlayerPlatformView] on Android:
/// a per-view [FlutterMethodChannel] named
/// `com.x87player/ios_player_view/<viewId>` is used for bidirectional
/// communication with the Flutter side.
///
/// Key AVPlayer settings that prevent the ~1-minute live-stream freeze:
///   - `automaticallyWaitsToMinimizeStalling = false` — prevents AVPlayer from
///     pausing to rebuild a large buffer on live IPTV streams.
///   - `preferredForwardBufferDuration = 3` — keeps the buffer small so the
///     player stays close to the live edge.
///
/// Stall recovery strategies:
///   - KVO on `AVPlayerItem.status` — on `.failed`, recreates the item and
///     seeks to the live edge.
///   - `.AVPlayerItemPlaybackStalled` — seeks to live edge and calls play().
///   - Periodic time observer every 0.5 s — detects when the playback position
///     has not advanced for 8+ seconds while supposedly playing.
/// A UIView subclass that automatically resizes its first sublayer
/// (the AVPlayerLayer) whenever the view's bounds change.
private class PlayerContainerView: UIView {
    override func layoutSubviews() {
        super.layoutSubviews()
        // Resize the AVPlayerLayer to fill the container.
        layer.sublayers?.first?.frame = bounds
    }
}

class IosPlayerPlatformView: NSObject, FlutterPlatformView {

    // MARK: - UI

    private let containerView: PlayerContainerView = {
        let v = PlayerContainerView()
        v.backgroundColor = .black
        return v
    }()

    // MARK: - Player

    private var player: AVPlayer?
    private var playerLayer: AVPlayerLayer?
    private var currentURL: URL?
    private var isMuted = false

    // MARK: - Observers / timers

    private var statusObserver: NSKeyValueObservation?
    private var timeObserverToken: Any?
    private var stalledObserver: NSObjectProtocol?
    private var endedObserver: NSObjectProtocol?
    private var lastPosition: CMTime = .zero
    private var stallCounter: Int = 0
    /// Number of 0.5 s ticks without position advance that triggers recovery
    /// (8 s / 0.5 s = 16 ticks).
    private static let stallTicks = 16

    // MARK: - Channel

    private let channel: FlutterMethodChannel

    // MARK: - Init

    init(frame: CGRect, viewId: Int64, messenger: FlutterBinaryMessenger, args: [String: Any]?) {
        channel = FlutterMethodChannel(
            name: "com.x87player/ios_player_view/\(viewId)",
            binaryMessenger: messenger
        )
        super.init()

        channel.setMethodCallHandler(handleMethodCall)

        // Tap recogniser → send onTapped to Flutter
        let tap = UITapGestureRecognizer(target: self, action: #selector(handleTap))
        containerView.addGestureRecognizer(tap)

        // Auto-play from creation params if a URL was provided.
        if let url = args?["url"] as? String, !url.isEmpty {
            let autoPlay = args?["autoPlay"] as? Bool ?? true
            loadURL(url, autoPlay: autoPlay)
        }
    }

    // MARK: - FlutterPlatformView

    func view() -> UIView { containerView }

    // MARK: - Method channel handler

    private func handleMethodCall(_ call: FlutterMethodCall, result: @escaping FlutterResult) {
        switch call.method {
        case "play":
            guard let args = call.arguments as? [String: Any],
                  let url = args["url"] as? String else {
                result(FlutterError(code: "INVALID_ARGS", message: "url is required", details: nil))
                return
            }
            loadURL(url, autoPlay: true)
            result(nil)

        case "pause":
            player?.pause()
            sendState()
            result(nil)

        case "resume":
            player?.play()
            sendState()
            result(nil)

        case "stop":
            stopPlayback()
            result(nil)

        case "setVolume":
            guard let args = call.arguments as? [String: Any],
                  let volume = args["volume"] as? Double else {
                result(FlutterError(code: "INVALID_ARGS", message: "volume is required", details: nil))
                return
            }
            player?.volume = Float(volume)
            result(nil)

        case "toggleMute":
            isMuted.toggle()
            player?.isMuted = isMuted
            result(nil)

        case "dispose":
            cleanup()
            result(nil)

        default:
            result(FlutterMethodNotImplemented)
        }
    }

    // MARK: - Playback control

    private func loadURL(_ urlString: String, autoPlay: Bool) {
        guard let url = URL(string: urlString) else { return }

        stopPlayback()
        currentURL = url

        let item = AVPlayerItem(url: url)
        // Small forward buffer keeps AVPlayer near the live edge instead of
        // trying to buffer a large VOD-style window.
        item.preferredForwardBufferDuration = 3

        let avPlayer = AVPlayer(playerItem: item)
        // Critical for live IPTV: prevents AVPlayer from pausing playback to
        // rebuild the buffer, which is the root cause of the ~1-minute freeze.
        avPlayer.automaticallyWaitsToMinimizeStalling = false
        avPlayer.isMuted = isMuted

        // Create/update the player layer.
        if let existing = playerLayer {
            existing.player = avPlayer
        } else {
            let layer = AVPlayerLayer(player: avPlayer)
            layer.videoGravity = .resizeAspect
            layer.frame = containerView.bounds
            containerView.layer.addSublayer(layer)
            playerLayer = layer
        }

        player = avPlayer

        // Observe item status for error recovery.
        statusObserver = item.observe(\.status, options: [.new]) { [weak self] item, _ in
            guard let self else { return }
            if item.status == .failed {
                self.recoverFromError()
            }
        }

        // Stall notification — seek to live edge and resume.
        stalledObserver = NotificationCenter.default.addObserver(
            forName: .AVPlayerItemPlaybackStalled,
            object: item,
            queue: .main
        ) { [weak self] _ in
            self?.seekToLiveEdgeAndPlay()
        }

        // End-of-stream notification.
        endedObserver = NotificationCenter.default.addObserver(
            forName: .AVPlayerItemDidPlayToEndTime,
            object: item,
            queue: .main
        ) { [weak self] _ in
            self?.sendState()
        }

        // Periodic time observer — detects position stalls.
        lastPosition = .zero
        stallCounter = 0
        timeObserverToken = avPlayer.addPeriodicTimeObserver(
            forInterval: CMTime(seconds: 0.5, preferredTimescale: 600),
            queue: .main
        ) { [weak self] time in
            self?.checkForPositionStall(currentTime: time)
            self?.sendState()
        }

        if autoPlay {
            avPlayer.play()
        }

        sendState(isBuffering: true)
    }

    private func stopPlayback() {
        player?.pause()
        removeObservers()
        player = nil
        currentURL = nil
        sendState()
    }

    private func removeObservers() {
        statusObserver?.invalidate()
        statusObserver = nil

        if let token = timeObserverToken, let p = player {
            p.removeTimeObserver(token)
        }
        timeObserverToken = nil

        if let obs = stalledObserver {
            NotificationCenter.default.removeObserver(obs)
        }
        stalledObserver = nil

        if let obs = endedObserver {
            NotificationCenter.default.removeObserver(obs)
        }
        endedObserver = nil
    }

    // MARK: - Stall & error recovery

    private func checkForPositionStall(currentTime: CMTime) {
        guard let p = player,
              p.timeControlStatus == .playing else {
            stallCounter = 0
            lastPosition = currentTime
            return
        }

        if currentTime == lastPosition {
            stallCounter += 1
            if stallCounter >= IosPlayerPlatformView.stallTicks {
                stallCounter = 0
                seekToLiveEdgeAndPlay()
            }
        } else {
            stallCounter = 0
            lastPosition = currentTime
        }
    }

    private func seekToLiveEdgeAndPlay() {
        guard let item = player?.currentItem,
              let range = item.seekableTimeRanges.last?.timeRangeValue else {
            player?.play()
            return
        }
        let liveEdge = CMTimeRangeGetEnd(range)
        player?.seek(to: liveEdge, toleranceBefore: .zero, toleranceAfter: .zero) { [weak self] _ in
            self?.player?.play()
            self?.stallCounter = 0
            self?.lastPosition = liveEdge
        }
    }

    private func recoverFromError() {
        guard let url = currentURL else { return }
        // Brief delay before recreating the item so the network has a moment
        // to recover from a transient error.
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) { [weak self] in
            self?.loadURL(url.absoluteString, autoPlay: true)
        }
    }

    // MARK: - State reporting

    private func sendState(isBuffering: Bool? = nil) {
        guard let p = player else {
            channel.invokeMethod("onPlaybackStateChanged", arguments: [
                "isPlaying": false,
                "isBuffering": false,
                "hasError": false,
                "errorMessage": "",
            ] as [String: Any])
            return
        }

        let playing = p.timeControlStatus == .playing
        let buffering = isBuffering ?? (p.timeControlStatus == .waitingToPlayAtSpecifiedRate)
        let item = p.currentItem
        let failed = item?.status == .failed
        let errMsg: String = item?.error?.localizedDescription ?? ""

        channel.invokeMethod("onPlaybackStateChanged", arguments: [
            "isPlaying": playing,
            "isBuffering": buffering,
            "hasError": failed,
            "errorMessage": errMsg,
        ] as [String: Any])
    }

    // MARK: - Gesture

    @objc private func handleTap() {
        channel.invokeMethod("onTapped", arguments: nil)
    }

    // MARK: - Cleanup

    private func cleanup() {
        stopPlayback()
        playerLayer?.removeFromSuperlayer()
        playerLayer = nil
        channel.setMethodCallHandler(nil)
    }
}
