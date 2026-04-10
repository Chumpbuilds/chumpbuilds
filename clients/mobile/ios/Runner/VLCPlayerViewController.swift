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

    /// Year of the content — used to narrow the subtitle search.
    var contentYear: String?

    /// TMDB ID of the content — used to narrow the subtitle search.
    var contentTmdbId: String?

    /// Season number (series only) — used for subtitle search.
    var contentSeason: Int?

    /// Episode number (series only) — used for subtitle search.
    var contentEpisode: Int?

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

    // MARK: - Subtitle / resolution controls

    private var subtitlesButton: UIButton!
    private var resolutionButton: UIButton!
    /// Local WebVTT files written for subtitle injection — deleted on dismiss.
    private var tempSubtitleURLs: [URL] = []

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
        cleanupTempSubtitles()
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

        // Subtitles button (top-right corner)
        subtitlesButton = UIButton(type: .system)
        let subtitleIcon: UIImage?
        if #available(iOS 15, *) {
            subtitleIcon = UIImage(systemName: "captions.bubble")
        } else {
            subtitleIcon = UIImage(systemName: "text.bubble")
        }
        subtitlesButton.setImage(subtitleIcon, for: .normal)
        subtitlesButton.tintColor = .white
        subtitlesButton.translatesAutoresizingMaskIntoConstraints = false
        subtitlesButton.addTarget(self, action: #selector(subtitlesTapped), for: .touchUpInside)
        controlsView.addSubview(subtitlesButton)

        // Resolution button (to the left of the subtitles button)
        resolutionButton = UIButton(type: .system)
        resolutionButton.setImage(UIImage(systemName: "rectangle.stack"), for: .normal)
        resolutionButton.tintColor = .white
        resolutionButton.translatesAutoresizingMaskIntoConstraints = false
        resolutionButton.addTarget(self, action: #selector(resolutionTapped), for: .touchUpInside)
        controlsView.addSubview(resolutionButton)

        let safeArea = view.safeAreaLayoutGuide
        NSLayoutConstraint.activate([
            dismissButton.topAnchor.constraint(equalTo: safeArea.topAnchor, constant: 12),
            dismissButton.leadingAnchor.constraint(equalTo: safeArea.leadingAnchor, constant: 16),
            dismissButton.widthAnchor.constraint(equalToConstant: 32),
            dismissButton.heightAnchor.constraint(equalToConstant: 32),

            titleLabel.centerYAnchor.constraint(equalTo: dismissButton.centerYAnchor),
            titleLabel.leadingAnchor.constraint(equalTo: dismissButton.trailingAnchor, constant: 12),
            titleLabel.trailingAnchor.constraint(equalTo: resolutionButton.leadingAnchor, constant: -8),

            subtitlesButton.topAnchor.constraint(equalTo: safeArea.topAnchor, constant: 12),
            subtitlesButton.trailingAnchor.constraint(equalTo: safeArea.trailingAnchor, constant: -16),
            subtitlesButton.widthAnchor.constraint(equalToConstant: 32),
            subtitlesButton.heightAnchor.constraint(equalToConstant: 32),

            resolutionButton.topAnchor.constraint(equalTo: safeArea.topAnchor, constant: 12),
            resolutionButton.trailingAnchor.constraint(equalTo: subtitlesButton.leadingAnchor, constant: -12),
            resolutionButton.widthAnchor.constraint(equalToConstant: 32),
            resolutionButton.heightAnchor.constraint(equalToConstant: 32),

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

    @objc private func subtitlesTapped() {
        controlsTimer?.invalidate()
        let wasPlaying = mediaPlayer?.isPlaying ?? false
        mediaPlayer?.pause()
        showSubtitlePicker(wasPlaying: wasPlaying)
    }

    @objc private func resolutionTapped() {
        controlsTimer?.invalidate()
        let wasPlaying = mediaPlayer?.isPlaying ?? false
        mediaPlayer?.pause()
        showResolutionPicker(wasPlaying: wasPlaying)
    }

    // MARK: - Subtitle picker

    private func showSubtitlePicker(wasPlaying: Bool) {
        guard let title = streamTitle, !title.isEmpty else {
            presentSimpleAlert(title: "Subtitles", message: "No content title available for subtitle search.") {
                if wasPlaying { self.mediaPlayer?.play() }
                self.scheduleHideControls()
            }
            return
        }

        // Read preferred languages from UserDefaults — Flutter shared_preferences
        // stores them under "flutter.subtitle_languages" as a JSON array string.
        var langs: [String] = ["en"]
        if let json = UserDefaults.standard.string(forKey: "flutter.subtitle_languages"),
           let data = json.data(using: .utf8),
           let arr = (try? JSONSerialization.jsonObject(with: data)) as? [String],
           !arr.isEmpty {
            langs = arr
        }

        let loadingAlert = UIAlertController(
            title: "Subtitles",
            message: "Searching for subtitles…",
            preferredStyle: .alert
        )
        present(loadingAlert, animated: true)

        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self else { return }

            struct SubtitleResult {
                let fileId: Int
                let language: String
                let release: String
                let downloadCount: Int
                let provider: String
            }

            var allResults: [SubtitleResult] = []

            for lang in langs {
                var components = URLComponents(string: "https://x87player.xyz/subtitles/search")!
                var queryItems: [URLQueryItem] = [URLQueryItem(name: "title", value: title)]
                if let year = self.contentYear { queryItems.append(URLQueryItem(name: "year", value: year)) }
                if let tmdbId = self.contentTmdbId { queryItems.append(URLQueryItem(name: "tmdb_id", value: tmdbId)) }
                if let season = self.contentSeason { queryItems.append(URLQueryItem(name: "season", value: "\(season)")) }
                if let episode = self.contentEpisode { queryItems.append(URLQueryItem(name: "episode", value: "\(episode)")) }
                queryItems.append(URLQueryItem(name: "lang", value: lang))
                components.queryItems = queryItems

                guard let url = components.url else { continue }

                let sem = DispatchSemaphore(value: 0)
                var request = URLRequest(url: url, timeoutInterval: 15)
                request.httpMethod = "GET"
                URLSession.shared.dataTask(with: request) { data, response, _ in
                    defer { sem.signal() }
                    guard
                        let data,
                        (response as? HTTPURLResponse)?.statusCode == 200,
                        let arr = (try? JSONSerialization.jsonObject(with: data)) as? [[String: Any]]
                    else { return }
                    for item in arr {
                        guard let fileId = item["file_id"] as? Int else { continue }
                        allResults.append(SubtitleResult(
                            fileId: fileId,
                            language: item["language"] as? String ?? lang,
                            release: item["release"] as? String ?? "",
                            downloadCount: item["download_count"] as? Int ?? 0,
                            provider: item["provider"] as? String ?? "OpenSubtitles"
                        ))
                    }
                }.resume()
                sem.wait()
            }

            DispatchQueue.main.async { [weak self] in
                guard let self else { return }
                loadingAlert.dismiss(animated: false) {
                    if allResults.isEmpty {
                        self.presentSimpleAlert(title: "Subtitles", message: "No subtitles found.") {
                            if wasPlaying { self.mediaPlayer?.play() }
                            self.scheduleHideControls()
                        }
                        return
                    }

                    let sheet = UIAlertController(title: "Subtitles", message: nil, preferredStyle: .actionSheet)
                    sheet.addAction(UIAlertAction(title: "Off", style: .default) { _ in
                        // Disable all subtitle tracks in VLC
                        self.mediaPlayer?.currentVideoSubTitleIndex = -1
                        if wasPlaying { self.mediaPlayer?.play() }
                        self.scheduleHideControls()
                    })
                    for r in allResults {
                        let badge = r.downloadCount > 0 ? " (↓\(r.downloadCount))" : ""
                        let tag = r.provider.lowercased() == "subs.ro" ? "🟨" : "🟦"
                        let label = "\(tag) [\(r.language.uppercased())] \(r.release)\(badge)  (\(r.provider))"
                        sheet.addAction(UIAlertAction(title: label, style: .default) { [weak self] _ in
                            self?.downloadAndInjectSubtitle(
                                fileId: r.fileId,
                                language: r.language,
                                resumePlayback: wasPlaying
                            )
                        })
                    }
                    sheet.addAction(UIAlertAction(title: "Cancel", style: .cancel) { _ in
                        if wasPlaying { self.mediaPlayer?.play() }
                        self.scheduleHideControls()
                    })
                    if let pop = sheet.popoverPresentationController {
                        pop.sourceView = self.subtitlesButton
                        pop.sourceRect = self.subtitlesButton.bounds
                    }
                    self.present(sheet, animated: true)
                }
            }
        }
    }

    private func downloadAndInjectSubtitle(fileId: Int, language: String, resumePlayback: Bool) {
        let loadingAlert = UIAlertController(
            title: "Subtitles",
            message: "Downloading subtitle…",
            preferredStyle: .alert
        )
        present(loadingAlert, animated: true)

        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self else { return }

            var srtContent: String?
            let downloadURL = URL(string: "https://x87player.xyz/subtitles/download?file_id=\(fileId)")!
            var request = URLRequest(url: downloadURL, timeoutInterval: 60)
            request.httpMethod = "GET"

            let sem = DispatchSemaphore(value: 0)
            URLSession.shared.dataTask(with: request) { data, response, _ in
                defer { sem.signal() }
                guard let data, (response as? HTTPURLResponse)?.statusCode == 200 else { return }
                srtContent = String(data: data, encoding: .utf8)
                    ?? String(data: data, encoding: .isoLatin1)
            }.resume()
            sem.wait()

            DispatchQueue.main.async { [weak self] in
                guard let self else { return }
                loadingAlert.dismiss(animated: false) {
                    guard let srt = srtContent,
                          !srt.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                    else {
                        self.presentSimpleAlert(title: "Subtitles", message: "Failed to download subtitle.") {
                            if resumePlayback { self.mediaPlayer?.play() }
                            self.scheduleHideControls()
                        }
                        return
                    }
                    self.injectSubtitle(srtContent: srt, language: language, resumePlayback: resumePlayback)
                }
            }
        }
    }

    private func injectSubtitle(srtContent: String, language: String, resumePlayback: Bool) {
        let vttContent = srtToWebVTT(srtContent)
        let fileName = "subtitle_\(language)_\(Int(Date().timeIntervalSince1970)).vtt"
        let fileURL = FileManager.default.temporaryDirectory.appendingPathComponent(fileName)

        do {
            try vttContent.write(to: fileURL, atomically: true, encoding: .utf8)
        } catch {
            presentSimpleAlert(title: "Subtitles", message: "Failed to save subtitle file.") {
                if resumePlayback { self.mediaPlayer?.play() }
                self.scheduleHideControls()
            }
            return
        }

        tempSubtitleURLs.append(fileURL)
        mediaPlayer?.addPlaybackSlave(fileURL, type: .subtitle, enforce: true)

        if resumePlayback { mediaPlayer?.play() }
        scheduleHideControls()
    }

    // MARK: - SRT → WebVTT converter

    private func srtToWebVTT(_ srt: String) -> String {
        // Strip UTF-8 BOM if present
        var content = srt.hasPrefix("\u{FEFF}") ? String(srt.dropFirst()) : srt

        // Normalise line endings
        content = content.replacingOccurrences(of: "\r\n", with: "\n")
        content = content.replacingOccurrences(of: "\r", with: "\n")

        // Convert SRT timestamp separators: HH:MM:SS,mmm → HH:MM:SS.mmm
        if let regex = try? NSRegularExpression(pattern: #"(\d{2}:\d{2}:\d{2}),(\d{3})"#) {
            let range = NSRange(content.startIndex..., in: content)
            content = regex.stringByReplacingMatches(
                in: content, range: range, withTemplate: "$1.$2"
            )
        }

        return "WEBVTT\n\n" + content
    }

    // MARK: - Resolution / quality picker

    private func showResolutionPicker(wasPlaying: Bool) {
        guard let player = mediaPlayer else { return }

        let names = player.videoTrackNames as? [String] ?? []
        let indices = player.videoTrackIndexes as? [Int] ?? []

        let sheet = UIAlertController(title: "Quality", message: nil, preferredStyle: .actionSheet)

        if names.isEmpty || indices.isEmpty {
            sheet.addAction(UIAlertAction(title: "Auto (only option)", style: .default) { _ in
                if wasPlaying { self.mediaPlayer?.play() }
                self.scheduleHideControls()
            })
        } else {
            for (idx, name) in zip(indices, names) {
                let isSelected = Int32(idx) == player.currentVideoTrackIndex
                let label = (isSelected ? "▶ " : "") + name
                sheet.addAction(UIAlertAction(title: label, style: .default) { _ in
                    self.mediaPlayer?.currentVideoTrackIndex = Int32(idx)
                    if wasPlaying { self.mediaPlayer?.play() }
                    self.scheduleHideControls()
                })
            }
        }

        sheet.addAction(UIAlertAction(title: "Cancel", style: .cancel) { _ in
            if wasPlaying { self.mediaPlayer?.play() }
            self.scheduleHideControls()
        })

        if let pop = sheet.popoverPresentationController {
            pop.sourceView = resolutionButton
            pop.sourceRect = resolutionButton.bounds
        }

        present(sheet, animated: true)
    }

    // MARK: - Helpers

    private func presentSimpleAlert(title: String, message: String, completion: (() -> Void)? = nil) {
        let alert = UIAlertController(title: title, message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "OK", style: .default) { _ in completion?() })
        present(alert, animated: true)
    }

    private func cleanupTempSubtitles() {
        for url in tempSubtitleURLs {
            try? FileManager.default.removeItem(at: url)
        }
        tempSubtitleURLs.removeAll()
    }

    // MARK: - Time formatting

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
