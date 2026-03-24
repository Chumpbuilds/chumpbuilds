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

        let avPlayer = AVPlayer(url: url)
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

        // Observe end of playback so we can auto-dismiss
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(playerItemDidReachEnd),
            name: .AVPlayerItemDidPlayToEndTime,
            object: avPlayer.currentItem
        )
    }

    @objc private func playerItemDidReachEnd(_ notification: Notification) {
        DispatchQueue.main.async { [weak self] in
            self?.dismiss(animated: true, completion: nil)
        }
    }

    // MARK: - Cleanup

    private func cleanUp() {
        NotificationCenter.default.removeObserver(self)
        player?.pause()
        playerViewController?.player = nil
        player = nil
    }

    deinit {
        cleanUp()
    }
}
