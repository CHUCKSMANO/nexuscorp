import NexusCore
import SwiftUI

/// The first screen. Answers three questions in order: is it safe, where is the
/// money, what is each desk doing.
public struct DashboardView: View {
    @ObservedObject var state: AppState

    public var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {

                DeskHeader(
                    "Overview",
                    title: "Your edge in every desk.",
                    subtitle: "One hub that allocates to yield, trades, and copy-trading — all simulated."
                )

                // 1. Safety, stated plainly. This is the one thing that must never
                // be ambiguous, so it is words rather than a colour.
                safetyBanner

                // 2. The four desks, in the order money flows.
                VStack(alignment: .leading, spacing: Theme.gap) {
                    SectionHeader("Your desks")
                    LazyVGrid(
                        columns: [GridItem(.adaptive(minimum: 230), spacing: Theme.gap)],
                        spacing: Theme.gap
                    ) {
                        deskCards
                    }
                }

                // 3. What you currently hold.
                openPositions

                // 4. Anything that went wrong, most recent first.
                recentActivity
            }
            .padding(Theme.pagePadding)
        }
    }

    // MARK: - Safety

    @ViewBuilder
    private var safetyBanner: some View {
        let frozen = state.health?.frozen.all == true
        let color = frozen ? Theme.red : Theme.green
        HStack(spacing: 12) {
            Image(systemName: frozen ? "pause.circle.fill" : "checkmark.circle.fill")
                .font(.system(size: 16))
                .foregroundColor(color)
                .frame(width: 38, height: 38)
                .background(
                    RoundedRectangle(cornerRadius: 11, style: .continuous)
                        .fill(color.opacity(0.14))
                )

            VStack(alignment: .leading, spacing: 2) {
                Text(frozen ? "Everything is stopped" : "Simulation mode — no real money")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(Theme.ink)
                Text(frozen
                     ? "No desk can buy or sell until you resume them on the Settings tab."
                     : "Trades are simulated. Nothing here spends real money.")
                    .font(Theme.caption)
                    .foregroundColor(Theme.muted)
            }

            Spacer(minLength: 8)
        }
        .card()
    }

    // MARK: - Desks

    @ViewBuilder
    private var deskCards: some View {
        DeskCard(
            title: "Yield",
            icon: "percent",
            detail: yieldDetail,
            accent: Theme.green,
            frozen: state.health?.frozen.yield == true
        )
        DeskCard(
            title: "Trade",
            icon: "chart.line.uptrend.xyaxis",
            detail: tradeDetail,
            accent: Theme.blue,
            frozen: state.health?.frozen.all == true
        )
        DeskCard(
            title: "Copy",
            icon: "person.2",
            detail: copyDetail,
            accent: Theme.violet,
            frozen: state.health?.frozen.copy == true
        )
        DeskCard(
            title: "Wallet",
            icon: "banknote",
            detail: walletDetail,
            accent: Theme.gold,
            frozen: false
        )
    }

    private var yieldDetail: String {
        guard let project = state.yieldStatus?.position?.project ?? state.yieldStatus?.best?.project else {
            return "Nothing earning yet"
        }
        return "\(Formatters.pct(currentApy)) from \(project)"
    }

    private var currentApy: Double? {
        state.yieldStatus?.position?.apy ?? state.yieldStatus?.best?.apy
    }

    private var tradeDetail: String {
        let count = state.trade?.open_positions ?? 0
        if count == 0 { return "No open trades" }
        return "\(count) open · \(Formatters.usd(state.trade?.open_mark_usd))"
    }

    private var copyDetail: String {
        let count = state.copyStatus?.open_positions ?? 0
        if count == 0 { return "Copying nobody right now" }
        return "\(count) copied from \(state.followedWallets.count) wallets"
    }

    private var walletDetail: String {
        "\(Formatters.usd(state.wallet?.cash_usd)) ready to spend"
    }

    // MARK: - Positions

    private var allPositions: [Position] {
        (state.trade?.positions ?? []) + state.copyPositions
    }

    private var openPositions: some View {
        Panel("What you're holding", subtitle: "Close a position to take it back into cash.") {
            RowList(
                count: allPositions.count,
                empty: {
                    EmptyState(
                        icon: "tray",
                        title: "No open positions",
                        message: "Positions you open on the Trade or Copy tab will appear here."
                    )
                }
            ) {
                ForEach(allPositions.prefix(8)) { pos in
                    TableRow {
                        HStack(spacing: 6) {
                            Text(pos.symbol ?? Formatters.shortAddress(pos.mint))
                                .font(.system(size: 13, weight: .medium))
                                .foregroundColor(Theme.ink)
                            Tag(pos.desk == "copy" ? "Copied" : "Yours", color: pos.desk == "copy" ? Theme.violetLt : Theme.blue)
                        }
                    } trailing: {
                        HStack(spacing: 10) {
                            Text(Formatters.usd(pos.mark_usd ?? pos.cost_usd))
                                .font(Theme.bodyNumber)
                                .foregroundColor(Theme.ink)
                            Text(signedUsd(pos.unrealized_pnl_usd))
                                .font(Theme.bodyNumber)
                                .foregroundColor(Theme.pnl(pos.unrealized_pnl_usd ?? 0))
                                .frame(width: 78, alignment: .trailing)

                            Button("Close") {
                                Task { await state.closePosition(desk: pos.desk ?? "trade", mint: pos.mint) }
                            }
                            .buttonStyle(ScoutGhostButtonStyle())
                            .controlSize(.small)
                        }
                    }
                }
            }
        }
    }

    // MARK: - Activity

    private var recentActivity: some View {
        Panel("Recent activity") {
            if state.eventLogs.isEmpty {
                EmptyState(icon: "clock", title: "Nothing has happened yet")
            } else {
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(state.eventLogs.prefix(8), id: \.self) { line in
                        Text(line)
                            .font(Theme.code)
                            .foregroundColor(logColor(line))
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                .padding(.top, 2)
            }
        }
    }

    private func logColor(_ line: String) -> Color {
        let lowered = line.lowercased()
        if lowered.contains("failed") || lowered.contains("error") { return Theme.loss }
        if lowered.contains("frozen") || lowered.contains("stopped") { return Theme.loss }
        return Theme.muted
    }

    private func signedUsd(_ value: Double?) -> String {
        guard let value else { return "--" }
        return (value >= 0 ? "+" : "") + Formatters.usd(value)
    }
}
