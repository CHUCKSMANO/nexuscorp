import Foundation
import Combine

@MainActor
public final class BackendManager: ObservableObject {
    @Published public var isRunning: Bool = false
    @Published public var isStarting: Bool = false
    @Published public var pid: Int32? = nil
    @Published public var logTail: String = "No logs yet."
    @Published public var statusMessage: String = "Stopped"

    private var process: Process?
    private let workspacePath: String
    private var healthCheckTimer: Timer?
    private var logWatchTimer: Timer?

    public init(workspacePath: String = "/Users/allthingschucks/Projects/nexuscorp") {
        self.workspacePath = workspacePath
        checkHealth()
        startPeriodicCheck()
    }

    deinit {
        healthCheckTimer?.invalidate()
        logWatchTimer?.invalidate()
    }

    public func startPeriodicCheck() {
        healthCheckTimer?.invalidate()
        healthCheckTimer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.checkHealth()
            }
        }
    }

    public func checkHealth() {
        Task {
            guard let url = URL(string: "http://127.0.0.1:8000/health") else { return }
            var req = URLRequest(url: url)
            req.timeoutInterval = 2.0
            do {
                let (_, response) = try await URLSession.shared.data(for: req)
                if let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) {
                    self.isRunning = true
                    self.statusMessage = "Online"
                } else {
                    self.isRunning = false
                    self.statusMessage = "Offline (status \( (response as? HTTPURLResponse)?.statusCode ?? 0 ))"
                }
            } catch {
                self.isRunning = false
                self.statusMessage = "Offline"
            }
            self.refreshLogs()
        }
    }

    public func startBackend() {
        guard !isRunning, !isStarting else { return }
        isStarting = true
        statusMessage = "Launching Python backend..."

        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self else { return }
            let task = Process()
            let venvPython = "\(self.workspacePath)/.venv/bin/python"
            let systemPython = "/usr/bin/python3"
            let pythonPath = FileManager.default.fileExists(atPath: venvPython) ? venvPython : systemPython

            task.executableURL = URL(fileURLWithPath: pythonPath)
            task.arguments = ["app.py"]
            task.currentDirectoryURL = URL(fileURLWithPath: self.workspacePath)

            let env = ProcessInfo.processInfo.environment
            task.environment = env

            let pipe = Pipe()
            task.standardOutput = pipe
            task.standardError = pipe

            do {
                try task.run()
                DispatchQueue.main.async {
                    self.process = task
                    self.pid = task.processIdentifier
                    self.statusMessage = "Started (PID \(task.processIdentifier))"
                    self.isStarting = false
                    self.isRunning = true
                    self.startLogWatcher()
                }
            } catch {
                DispatchQueue.main.async {
                    self.isStarting = false
                    self.statusMessage = "Launch failed: \(error.localizedDescription)"
                }
            }
        }
    }

    public func stopBackend() {
        statusMessage = "Stopping backend..."
        if let proc = process, proc.isRunning {
            proc.terminate()
            self.process = nil
        }

        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let killTask = Process()
            killTask.executableURL = URL(fileURLWithPath: "/bin/sh")
            killTask.arguments = ["-c", "lsof -ti tcp:8000 | xargs kill 2>/dev/null || true"]
            try? killTask.run()
            killTask.waitUntilExit()

            DispatchQueue.main.async {
                self?.isRunning = false
                self?.pid = nil
                self?.statusMessage = "Stopped"
                self?.checkHealth()
            }
        }
    }

    public func refreshLogs() {
        let appOut = "\(workspacePath)/logs/app.out"
        let appErr = "\(workspacePath)/logs/app.err"

        var output = ""
        if let errContent = try? String(contentsOfFile: appErr, encoding: .utf8), !errContent.isEmpty {
            let lines = errContent.components(separatedBy: .newlines).suffix(15).joined(separator: "\n")
            if !lines.isEmpty {
                output += "=== STDERR ===\n\(lines)\n\n"
            }
        }
        if let outContent = try? String(contentsOfFile: appOut, encoding: .utf8), !outContent.isEmpty {
            let lines = outContent.components(separatedBy: .newlines).suffix(25).joined(separator: "\n")
            output += "=== STDOUT ===\n\(lines)"
        }

        if !output.isEmpty {
            self.logTail = output
        }
    }

    private func startLogWatcher() {
        logWatchTimer?.invalidate()
        logWatchTimer = Timer.scheduledTimer(withTimeInterval: 3.0, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.refreshLogs()
            }
        }
    }
}
