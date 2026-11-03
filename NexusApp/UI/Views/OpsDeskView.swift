import NexusCore
import SwiftUI

/// Settings and safety controls. This is the page that has to be unambiguous:
/// one switch stops everything, and it says exactly that.
public struct OpsDeskView: View {
    @ObservedObject var state: AppState

    public var body: some View {
        VStack(spacing: 0) {
            DeskHeader(
                "Settings",
                title: "Stop things and see logs.",
                subtitle: "One control pauses every desk. Nothing trades until you resume."
            )
            .padding(.horizontal, Theme.pagePadding)
            .padding(.top, 22)
            .padding(.bottom, 16)

            HSplitView {
                controls
                logs
            }
        }
    }

    // MARK: - Controls

    private var controls: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {

                // The big one. Stop everything, and say what it means.
                Panel("Stop everything", subtitle: "Pauses Yield, Finder and Copy. Nothing can trade until you resume.") {
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            StateBadge(state.health?.frozen.all == true ? .frozen : .running)
                            Text(state.health?.frozen.all == true
                                 ? "Everything is paused"
                                 : "Everything is running")
                                .font(.system(size: 13, weight: .medium))
                                .foregroundColor(Theme.ink)
                            Spacer()
                        }
                        HStack {
                            Button("Stop everything") {
                                Task { await state.freezeAll() }
                            }
                            .buttonStyle(ScoutDangerButtonStyle())
                            .disabled(state.health?.frozen.all == true)

                            Button("Resume everything") {
                                Task { await state.thawAll() }
                            }
                            .buttonStyle(ScoutGhostButtonStyle())
                            .disabled(state.health?.frozen.all != true)
                        }
                    }
                }

                // Per-desk, in the same words.
                Panel("Each desk separately") {
                    VStack(spacing: 0) {
                        ForEach(["yield", "finder", "copy"], id: \.self) { desk in
                            deskRow(desk)
                        }
                    }
                }

                serverPanel
            }
            .padding(Theme.pagePadding)
        }
        .frame(minWidth: 380, idealWidth: 430)
        .background(Theme.bg)
    }

    private func deskRow(_ desk: String) -> some View {
        let isFrozen = frozen(desk)
        return TableRow {
            HStack(spacing: 8) {
                Text(desk.capitalized)
                    .font(.system(size: 13, weight: .medium))
                    .foregroundColor(Theme.ink)
                StateBadge(isFrozen ? .frozen : .running)
            }
        } trailing: {
            Button(isFrozen ? "Resume" : "Stop") {
                Task {
                    if isFrozen {
                        await state.thawDesk(desk)
                    } else {
                        await state.freezeDesk(desk)
                    }
                }
            }
            .buttonStyle(isFrozen ? AnyButtonStyle(ScoutPrimaryButtonStyle()) : AnyButtonStyle(ScoutGhostButtonStyle()))
            .controlSize(.small)
        }
    }

    private var serverPanel: some View {
        Panel("Server", subtitle: "The app talks to a small Python program running on this Mac.") {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 8) {
                    StateBadge(state.backendManager.isRunning ? .running : .stopped)
                    Text(state.backendManager.statusMessage)
                        .font(Theme.body)
                        .foregroundColor(Theme.ink)
                    Spacer()
                }
                if let pid = state.backendManager.pid {
                    Text("Process \(pid)")
                        .font(Theme.captionNumber)
                        .foregroundColor(Theme.dim)
                }
                HStack {
                    Button("Start server") { state.backendManager.startBackend() }
                        .buttonStyle(ScoutPrimaryButtonStyle())
                        .disabled(state.backendManager.isRunning || state.backendManager.isStarting)
                    Button("Stop server") { state.backendManager.stopBackend() }
                        .buttonStyle(ScoutGhostButtonStyle())
                        .disabled(!state.backendManager.isRunning)
                }
            }
        }
    }

    // MARK: - Logs

    private var logs: some View {
        VStack(alignment: .leading, spacing: Theme.gap) {
            Panel("What just happened") {
                if state.eventLogs.isEmpty {
                    EmptyState(icon: "clock", title: "Nothing yet")
                } else {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 4) {
                            ForEach(state.eventLogs.prefix(40), id: \.self) { line in
                                Text(line)
                                    .font(Theme.code)
                                    .foregroundColor(logColor(line))
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .textSelection(.enabled)
                            }
                        }
                    }
                    .frame(maxHeight: 280)
                }
            }

            Panel("Server output") {
                if state.backendManager.logTail == "No logs yet." {
                    EmptyState(icon: "terminal", title: "No server output")
                } else {
                    ScrollView {
                        Text(state.backendManager.logTail)
                            .font(Theme.code)
                            .foregroundColor(Theme.muted)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .textSelection(.enabled)
                    }
                    .frame(maxHeight: 320)
                }
            }

            Spacer(minLength: 0)
        }
        .padding(Theme.pagePadding)
        .background(Theme.bg)
    }

    private func frozen(_ desk: String) -> Bool {
        switch desk {
        case "yield": return state.health?.frozen.yield == true
        case "finder": return state.health?.frozen.finder == true
        case "copy": return state.health?.frozen.copy == true
        default: return state.health?.frozen.all == true
        }
    }

    private func logColor(_ line: String) -> Color {
        let lowered = line.lowercased()
        if lowered.contains("failed") || lowered.contains("error") { return Theme.loss }
        if lowered.contains("frozen") || lowered.contains("stopped") { return Theme.loss }
        return Theme.muted
    }
}
