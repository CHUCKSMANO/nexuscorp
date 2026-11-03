import SwiftUI

@main
struct NexusCorpApp: App {
    var body: some Scene {
        WindowGroup {
            TerminalView()
                .preferredColorScheme(.dark)
        }
        .defaultSize(width: 1280, height: 860)
        .windowStyle(.hiddenTitleBar)
        .commands {
            CommandGroup(replacing: .newItem) {}
        }
    }
}

enum DeskTab: String, CaseIterable, Identifiable {
    case overview = "Overview"
    case yield = "Yield"
    case trade = "Trade"
    case copy = "Copy"
    case wallet = "Wallet"
    case settings = "Settings"

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .overview: return "square.grid.2x2"
        case .yield: return "percent"
        case .trade: return "chart.line.uptrend.xyaxis"
        case .copy: return "person.2"
        case .wallet: return "banknote"
        case .settings: return "gearshape"
        }
    }

    /// One line saying what this tab is for, shown above each desk.
    var blurb: String {
        switch self {
        case .overview: return "How everything is doing"
        case .yield: return "Earn interest on USDC"
        case .trade: return "Buy and sell tokens"
        case .copy: return "Mirror other wallets"
        case .wallet: return "Hold and move money"
        case .settings: return "Stop things and see logs"
        }
    }
}

struct TerminalView: View {
    @StateObject private var state = AppState()
    @State private var desk: DeskTab = .overview

    var body: some View {
        VStack(spacing: 0) {
            HeaderHUDView(state: state)
            deskNav

            Group {
                switch desk {
                case .overview:
                    DashboardView(state: state)
                case .yield:
                    YieldDeskView(state: state)
                case .trade:
                    TradeDeskView(state: state)
                case .copy:
                    CopyDeskView(state: state)
                case .wallet:
                    WalletDeskView(state: state)
                case .settings:
                    OpsDeskView(state: state)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .frame(minWidth: 980, minHeight: 680)
        .background(Theme.bg)
        .task {
            await state.bootstrap()
        }
    }

    // MARK: - Desk navigation

    private var deskNav: some View {
        HStack(spacing: 4) {
            ForEach(DeskTab.allCases) { tab in
                navButton(tab)
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, Theme.pagePadding)
        .padding(.vertical, 8)
        .background(Theme.bg)
        .overlay(alignment: .bottom) {
            Rectangle().fill(Theme.line).frame(height: 1)
        }
    }

    private func navButton(_ tab: DeskTab) -> some View {
        let active = desk == tab
        return Button {
            desk = tab
        } label: {
            HStack(spacing: 7) {
                Image(systemName: tab.icon)
                    .font(.system(size: 12, weight: .semibold))
                Text(tab.rawValue)
                    .font(.system(size: 13, weight: .semibold))
            }
            .foregroundColor(active ? Theme.ink : Theme.muted)
            .padding(.horizontal, 13)
            .padding(.vertical, 7)
            .background(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .fill(active ? Theme.violet.opacity(0.16) : .clear)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .stroke(active ? Theme.violet.opacity(0.45) : .clear, lineWidth: 1)
            )
            .contentShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
        }
        .buttonStyle(.plain)
    }
}
