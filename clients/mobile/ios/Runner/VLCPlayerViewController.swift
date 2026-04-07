import UIKit
import MobileVLCKit

/// Fullscreen video player backed by MobileVLCKit.
///
/// Used for VOD content (movies and series) on iOS. VLCKit includes software
/// decoders for every codec — H.264, HEVC hev1/hvc1, AC3, DTS, etc. — so it
/// plays streams that AVPlayer cannot handle (e.g. HEVC inside .mp4 containers
/// that use the hev1 codec-tag signalling).
///
/// Live TV continues to use [NativePlayerViewController] (AVPlayer) which is
/// better suited for low-latency HLS live streams.
class VLCPlayerViewController: UIViewController {

    // MARK: - Public

    /// The stream URL to play.
    var streamURL: URL?

    /// Human-readable title shown in the player UI.
    var streamTitle: String?

    /// Called when the player is dismissed (by the user or at end of stream).
    var onDismissed: (() -> Void)?

    // MARK: - Private

    private var mediaPlayer: VLCMediaPlayer?
    private var videoView: UIView!
    private var controlsView: UIView!
    private var titleLabel: UILabel!
    private var playPauseButton: UIButton!
    private var seekBar: UISlider!
    private var timeLabel: UILabel!
    private var dismissButton: UIButton!
    private var loadingIndicator: UIActivityIndicatorView!
    private var controlsTimer: Timer?
    private var isControlsVisible = true
    private var hasStartedPlayback = false

    private static let httpUserAgent =
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    private static let controlsHideDelay: TimeInterval = 3.5

    // MARK: - Lifecycle

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        setupVideoView()
        setupControls()
        setupGestures()
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        setupPlayer()
    }

    override func viewDidDisappear(_ animated: Bool) {
        super.viewDidDisappear(animated)
        mediaPlayer?.stop()
        mediaPlayer?.delegate = nil
        mediaPlayer = nil
        onDismissed?()
    }

    override var prefersStatusBarHidden: Bool { return true }

    override var supportedInterfaceOrientations: UIInterfaceOrientationMask {
        return .landscape
    }

    // MARK: - Setup

    private func setupVideoView() {
        videoView = UIView()
        videoView.backgroundColor = .black
        videoView.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(videoView)
        NSLayoutConstraint.activate([
            videoView.topAnchor.constraint(equalTo: view.topAnchor),
            videoView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            videoView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            videoView.bottomAnchor.constraint(equalTo: view.bottomAnchor),
        ])
    }

    private func setupControls() {
        // Semi-transparent overlay
        controlsView = UIView()
        controlsView.backgroundColor = UIColor.black.withAlphaComponent(0.55)
        controlsView.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(controlsView)
        NSLayoutConstraint.activate([
            controlsView.topAnchor.constraint(equalTo: view.topAnchor),
            controlsView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            controlsView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            controlsView.bottomAnchor.constraint(equalTo: view.bottomAnchor),
        ])

        // Dismiss button (top-left)
        dismissButton = UIButton(type: .system)
        dismissButton.setImage(UIImage(systemName: "xmark"), for: .normal)
        dismissButton.tintColor = .white
        dismissButton.translatesAutoresizingMaskIntoConstraints = false
        dismissButton.addTarget(self, action: #selector(dismissTapped), for: .touchUpInside)
        controlsView.addSubview(dismissButton)

        // Title label
        titleLabel = UILabel()
        titleLabel.textColor = .white
        titleLabel.font = UIFont.systemFont(ofSize: 16, weight: .semibold)
        titleLabel.text = streamTitle ?? ""
        titleLabel.translatesAutoresizingMaskIntoConstraints = false
        controlsView.addSubview(titleLabel)

        // Play/pause button (center)
        playPauseButton = UIButton(type: .system)
        playPauseButton.setImage(UIImage(systemName: "pause.fill"), for: .normal)
        playPauseButton.tintColor = .white
        playPauseButton.contentVerticalAlignment = .fill
        playPauseButton.contentHorizontalAlignment = .fill
        playPauseButton.translatesAutoresizingMaskIntoConstraints = false
        playPauseButton.addTarget(self, action: #selector(playPauseTapped), for: .touchUpInside)
        controlsView.addSubview(playPauseButton)

        // Seek bar
        seekBar = UISlider()
        seekBar.minimumTrackTintColor = .white
        seekBar.maximumTrackTintColor = UIColor.white.withAlphaComponent(0.4)
        seekBar.thumbTintColor = .white
        seekBar.translatesAutoresizingMaskIntoConstraints = false
        seekBar.addTarget(self, action: #selector(seekBarChanged), for: .valueChanged)
        controlsView.addSubview(seekBar)

        // Time label
        timeLabel = UILabel()
        timeLabel.textColor = .white
        timeLabel.font = UIFont.monospacedDigitSystemFont(ofSize: 12, weight: .regular)
        timeLabel.text = "0:00"
        timeLabel.translatesAutoresizingMaskIntoConstraints = false
        controlsView.addSubview(timeLabel)

        // Loading indicator
        loadingIndicator = UIActivityIndicatorView(style: .large)
        loadingIndicator.color = .white
        loadingIndicator.translatesAutoresizingMaskIntoConstraints = false
        loadingIndicator.hidesWhenStopped = true
        view.addSubview(loadingIndicator)

        let safeArea = view.safeAreaLayoutGuide
        NSLayoutConstraint.activate([
            dismissButton.topAnchor.constraint(equalTo: safeArea.topAnchor, constant: 12),
            dismissButton.leadingAnchor.constraint(equalTo: safeArea.leadingAnchor, constant: 16),
            dismissButton.widthAnchor.constraint(equalToConstant: 32),
            dismissButton.heightAnchor.constraint(equalToConstant: 32),

            titleLabel.centerYAnchor.constraint(equalTo: dismissButton.centerYAnchor),
            titleLabel.leadingAnchor.constraint(equalTo: dismissButton.trailingAnchor, constant: 12),
            titleLabel.trailingAnchor.constraint(equalTo: safeArea.trailingAnchor, constant: -16),

            playPauseButton.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            playPauseButton.centerYAnchor.constraint(equalTo: view.centerYAnchor),
            playPauseButton.widthAnchor.constraint(equalToConstant: 56),
            playPauseButton.heightAnchor.constraint(equalToConstant: 56),

            seekBar.leadingAnchor.constraint(equalTo: safeArea.leadingAnchor, constant: 16),
            seekBar.trailingAnchor.constraint(equalTo: safeArea.trailingAnchor, constant: -16),
            seekBar.bottomAnchor.constraint(equalTo: safeArea.bottomAnchor, constant: -40),

            timeLabel.leadingAnchor.constraint(equalTo: seekBar.leadingAnchor),
            timeLabel.topAnchor.constraint(equalTo: seekBar.bottomAnchor, constant: 4),

            loadingIndicator.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            loadingIndicator.centerYAnchor.constraint(equalTo: view.centerYAnchor),
        ])
    }

    private func setupGestures() {
        let tap = UITapGestureRecognizer(target: self, action: #selector(handleTap))
        videoView.addGestureRecognizer(tap)
    }

    private func setupPlayer() {
        guard let url = streamURL else { return }

        loadingIndicator.startAnimating()

        let media = VLCMedia(url: url)
        media.addOptions([
            "http-user-agent": VLCPlayerViewController.httpUserAgent,
            "http-referrer": "",
        ])

        let player = VLCMediaPlayer()
        player.media = media
        player.drawable = videoView
        player.delegate = self
        self.mediaPlayer = player

        player.play()
        scheduleHideControls()
    }

    // MARK: - Controls visibility

    private func scheduleHideControls() {
        controlsTimer?.invalidate()
        controlsTimer = Timer.scheduledTimer(withTimeInterval: VLCPlayerViewController.controlsHideDelay, repeats: false) { [weak self] _ in
            self?.hideControls()
        }
    }

    private func hideControls() {
        UIView.animate(withDuration: 0.3) {
            self.controlsView.alpha = 0
        }
        isControlsVisible = false
    }

    private func showControls() {
        UIView.animate(withDuration: 0.3) {
            self.controlsView.alpha = 1
        }
        isControlsVisible = true
        scheduleHideControls()
    }

    // MARK: - Actions

    @objc private func handleTap() {
        if isControlsVisible {
            hideControls()
        } else {
            showControls()
        }
    }

    @objc private func dismissTapped() {
        dismiss(animated: true, completion: nil)
    }

    @objc private func playPauseTapped() {
        guard let player = mediaPlayer else { return }
        if player.isPlaying {
            player.pause()
            playPauseButton.setImage(UIImage(systemName: "play.fill"), for: .normal)
        } else {
            player.play()
            playPauseButton.setImage(UIImage(systemName: "pause.fill"), for: .normal)
        }
        scheduleHideControls()
    }

    @objc private func seekBarChanged() {
        guard let player = mediaPlayer else { return }
        player.position = seekBar.value
        scheduleHideControls()
    }

    // MARK: - Helpers

    private func formatTime(_ ms: Int) -> String {
        let totalSeconds = ms / 1000
        let h = totalSeconds / 3600
        let m = (totalSeconds % 3600) / 60
        let s = totalSeconds % 60
        if h > 0 {
            return String(format: "%d:%02d:%02d", h, m, s)
        }
        return String(format: "%d:%02d", m, s)
    }
}

// MARK: - VLCMediaPlayerDelegate

extension VLCPlayerViewController: VLCMediaPlayerDelegate {

    func mediaPlayerStateChanged(_ aNotification: Notification) {
        guard let player = mediaPlayer else { return }

        DispatchQueue.main.async { [weak self] in
            guard let self = self else { return }

            switch player.state {
            case .playing:
                self.hasStartedPlayback = true
                self.loadingIndicator.stopAnimating()
                self.playPauseButton.setImage(UIImage(systemName: "pause.fill"), for: .normal)

            case .paused:
                self.playPauseButton.setImage(UIImage(systemName: "play.fill"), for: .normal)

            case .buffering:
                if !self.hasStartedPlayback {
                    self.loadingIndicator.startAnimating()
                }

            case .ended, .stopped:
                self.dismiss(animated: true, completion: nil)

            case .error:
                self.loadingIndicator.stopAnimating()
                self.showErrorAndDismiss()

            default:
                break
            }
        }
    }

    func mediaPlayerTimeChanged(_ aNotification: Notification) {
        guard let player = mediaPlayer else { return }

        DispatchQueue.main.async { [weak self] in
            guard let self = self else { return }

            // Update seek bar position (0.0 – 1.0)
            self.seekBar.value = player.position

            // Update time label
            let currentMs = Int(player.time.value ?? 0)
            let remainingMs = Int(player.remainingTime?.value ?? 0)
            let totalMs = currentMs + abs(remainingMs)
            if totalMs > 0 {
                self.timeLabel.text = "\(self.formatTime(currentMs)) / \(self.formatTime(totalMs))"
            } else {
                self.timeLabel.text = self.formatTime(currentMs)
            }
        }
    }

    // MARK: - Error handling

    private func showErrorAndDismiss() {
        let alert = UIAlertController(
            title: "Playback Error",
            message: "Unable to play this stream. The format may be unsupported.",
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "OK", style: .default) { [weak self] _ in
            self?.dismiss(animated: true, completion: nil)
        })
        present(alert, animated: true, completion: nil)
    }
}
