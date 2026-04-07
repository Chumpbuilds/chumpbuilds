import UIKit
import AVKit
import AVFoundation

/// Native iOS fullscreen video player.
///
/// Wraps [AVPlayerViewController] to deliver hardware-accelerated playback
/// via AVFoundation — the same path used by every first-party iOS video app.
///
/// Usage: present this view controller modally (or push it) with the stream
/// URL and an optional title. A completion callback is fired when the
/// user dismisses the player or playback ends.
class NativePlayerViewController: UIViewController {

    // MARK: - Public

    /// The stream URL to play.
    var streamURL: URL?

    /// Human-readable title shown in the native player UI.
    var streamTitle: String?

    /// Called when the player is dismissed (by the user or at end of stream).
    var onDismissed: (() -> Void)?

    // MARK: - Private

    private var player: AVPlayer?
    private var playerViewController: AVPlayerViewController?
    private var timeObserverToken: Any?
    private var itemStatusObserver: NSKeyValueObservation?

    // MARK: - Lifecycle

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        setupPlayer()
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        player?.play()
    }

    override func viewDidDisappear(_ animated: Bool) {
        super.viewDidDisappear(animated)
        cleanUp()
        onDismissed?()
    }

    // MARK: - Player setup

    private func setupPlayer() {
        guard let url = streamURL else { return }

        // Create a player item so we can tune live-stream buffer settings.
        let item = AVPlayerItem(url: url)
        // Keep a small forward buffer so AVPlayer stays close to the live edge
        // rather than accumulating a large VOD-style window.
        item.preferredForwardBufferDuration = 3

        let avPlayer = AVPlayer(playerItem: item)
        // Disabling automaticallyWaitsToMinimizeStalling prevents AVPlayer
        // from pausing to rebuild a large buffer on live IPTV streams — the
        // default behaviour causes the ~1-minute playback freeze.
        avPlayer.automaticallyWaitsToMinimizeStalling = false
        self.player = avPlayer

        let pvc = AVPlayerViewController()
        pvc.player = avPlayer
        pvc.showsPlaybackControls = true

        // Embed AVPlayerViewController as a child
        addChild(pvc)
        pvc.view.frame = view.bounds
        pvc.view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        view.addSubview(pvc.view)
        pvc.didMove(toParent: self)
        self.playerViewController = pvc

        // Observe item status — on failure attempt to recover.
        itemStatusObserver = item.observe(\.status, options: [.new]) { [weak self] observedItem, _ in
            guard let self = self else { return }
            if observedItem.status == .failed {
                print("[NativePlayer] Item failed: \(observedItem.error?.localizedDescription ?? "unknown")")
                DispatchQueue.main.async { self.recoverPlayback() }
            }
        }

        // Observe stalls so we can seek back to the live edge and resume.
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(playerItemDidStall),
            name: .AVPlayerItemPlaybackStalled,
            object: item
        )

        // Observe end of playback so we can auto-dismiss.
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(playerItemDidReachEnd),
            name: .AVPlayerItemDidPlayToEndTime,
            object: item
        )
    }

    // MARK: - Stall recovery

    @objc private func playerItemDidStall(_ notification: Notification) {
        print("[NativePlayer] Playback stalled – seeking to live edge")
        DispatchQueue.main.async { [weak self] in
            self?.recoverPlayback()
        }
    }

    private func recoverPlayback() {
        guard let player = player, let item = player.currentItem else { return }
        // Seek to the live edge (end of the last seekable time range) then resume.
        if let lastRange = item.seekableTimeRanges.last?.timeRangeValue,
           lastRange.end.isValid && !lastRange.end.isIndefinite {
            player.seek(
                to: lastRange.end,
                toleranceBefore: .positiveInfinity,
                toleranceAfter: .positiveInfinity
            ) { [weak player] _ in
                player?.play()
            }
        } else {
            player.play()
        }
    }

    @objc private func playerItemDidReachEnd(_ notification: Notification) {
        DispatchQueue.main.async { [weak self] in
            self?.dismiss(animated: true, completion: nil)
        }
    }

    // MARK: - Cleanup

    private func cleanUp() {
        NotificationCenter.default.removeObserver(self)
        itemStatusObserver?.invalidate()
        itemStatusObserver = nil
        if let token = timeObserverToken {
            player?.removeTimeObserver(token)
            timeObserverToken = nil
        }
        player?.pause()
        playerViewController?.player = nil
        player = nil
    }

    deinit {
        cleanUp()
    }
}
