import NexusCore
import SwiftUI

/// Copy trading: mirror what other people's wallets buy and sell.
public struct CopyDeskView: View {
    @ObservedObject var state: AppState
    @State private var address: String = ""
    @State private var label: String = ""

    public var body: some View {
        VStack(spacing: 0) {
            DeskHeader(
                "Copy",
                title: "Mirror other wallets.",
                subtitle: "Follow a Solana wallet and the Copy desk places the same trades, in simulation."
            )
            .padding(.horizontal, Theme.pagePadding)
            .padding(.top, 22)
            .padding(.bottom, 16)

            HSplitView {
                walletsPanel
                positionsPanel
            }
        }
    }

    // MARK: - Wallets you follow

    private var walletsPanel: some View {
        VStack(alignment: .leading, spacing: Theme.gap) {
            Panel("Wallets you follow", subtitle: "When one of these buys, the Copy desk does the same.") {
                VStack(alignment: .leading, spacing: 8) {
                    TextField("Solana wallet address", text: $address)
                        .scoutField()
                    TextField("Nickname (optional)", text: $label)
                        .scoutField()
                    Button("Follow wallet") { follow() }
                        .buttonStyle(ScoutPrimaryButtonStyle())
                        .disabled(address.trimmingCharacters(in: .whitespaces).isEmpty)
                }

                Divider().overlay(Theme.line)

                RowList(
                    count: state.followedWallets.count,
                    empty: {
                        EmptyState(
                            icon: "person.2",
                            title: "Not following anyone",
                            message: "Paste a wallet address above to start copying its trades."
                        )
                    }
                ) {
                    ForEach(state.followedWallets.keys.sorted(), id: \.self) { key in
                        TableRow {
                            HStack(spacing: 10) {
                                Image(systemName: "person.crop.circle")
                                    .font(.system(size: 15))
                                    .foregroundColor(Theme.violetLt)
                                VStack(alignment: .leading, spacing: 1) {
                                    Text(state.followedWallets[key]?.label ?? "Wallet")
                                        .font(.system(size: 13, weight: .medium))
                                        .foregroundColor(Theme.ink)
                                    Text(Formatters.shortAddress(key, size: 6))
                                        .font(Theme.code)
                                        .foregroundColor(Theme.dim)
                                }
                            }
                        } trailing: {
                            Button("Stop") {
                                Task { await state.unfollowWallet(address: key) }
                            }
                            .buttonStyle(ScoutGhostButtonStyle())
                            .controlSize(.small)
                        }
                    }
                }
            }

            Spacer(minLength: 0)
        }
        .padding(Theme.pagePadding)
        .frame(minWidth: 340, idealWidth: 400)
        .background(Theme.bg)
    }

    // MARK: - What copying produced

    private var positionsPanel: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                StatRow([
                    StatTile("Copied positions", value: "\(state.copyStatus?.open_positions ?? 0)"),
                    StatTile("Cash available", value: Formatters.usd(state.copyStatus?.cash_usd))
                ])

                Panel("Copied positions", subtitle: "Closed automatically when the wallet you follow sells.") {
                    RowList(
                        count: state.copyPositions.count,
                        empty: {
                            EmptyState(
                                icon: "tray",
                                title: "Nothing copied yet",
                                message: "Positions appear here when a wallet you follow buys."
                            )
                        }
                    ) {
                        ForEach(state.copyPositions) { pos in
                            TableRow {
                                Text(pos.symbol ?? Formatters.shortAddress(pos.mint))
                                    .font(.system(size: 13, weight: .medium))
                                    .foregroundColor(Theme.ink)
                            } trailing: {
                                HStack(spacing: 10) {
                                    Text(Formatters.usd(pos.mark_usd ?? pos.cost_usd))
                                        .font(Theme.bodyNumber)
                                        .foregroundColor(Theme.ink)
                                    Button("Close") {
                                        Task { await state.closePosition(desk: "copy", mint: pos.mint) }
                                    }
                                    .buttonStyle(ScoutGhostButtonStyle())
                                    .controlSize(.small)
                                }
                            }
                        }
                    }
                }

                Panel("Recent copies") {
                    fillsList(state.copyStatus?.recent_fills ?? [], emptyTitle: "No trades copied yet")
                }
            }
            .padding(Theme.pagePadding)
        }
        .background(Theme.bg)
    }

    private func follow() {
        let addr = address.trimmingCharacters(in: .whitespaces)
        guard !addr.isEmpty else { return }
        Task {
            await state.followWallet(address: addr, label: label.isEmpty ? "Wallet" : label)
            address = ""
            label = ""
        }
    }
}
