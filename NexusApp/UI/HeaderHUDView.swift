import NexusCore
import SwiftUI

/// The bar across the top: what this app is, whether it is safe, and the three
/// buttons you actually press.
public struct HeaderHUDView: View {
    @ObservedObject var state: AppState

    public var body: some View {
        VStack(spacing: 0) {
            navRow
            statBand
                .padding(.horizontal, Theme.pagePadding)
                .padding(.top, 16)
                .padding(.bottom, 18)
        }
        .background(Theme.nav)
        .overlay(alignment: .bottom) {
            Rectangle().fill(Theme.line).frame(height: 1)
        }
    }

    // MARK: - Nav row

    private var navRow: some View {
        HStack(spacing: 12) {
            brand

            Spacer(minLength: 12)

            HStack(spacing: 8) {
                // The single most important fact about this app: real money or a
                // simulation. It never changes colour, it is always spelled out.
                modePill

                if state.health?.frozen.all == true {
                    StateBadge(.frozen)
                }

                StateBadge(state.backendManager.isRunning ? .running : .stopped)
            }

            HStack(spacing: 8) {
                Button {
                    state.backendManager.isRunning
                        ? state.backendManager.stopBackend()
                        : state.backendManager.startBackend()
                } label: {
                    Text(state.backendManager.isRunning ? "Stop server" : "Start server")
                }
                .buttonStyle(state.backendManager.isRunning ? AnyButtonStyle(ScoutGhostButtonStyle()) : AnyButtonStyle(ScoutPrimaryButtonStyle()))

                Button {
                    Task { await state.refreshAll() }
                } label: {
                    if state.isRefreshing {
                        ProgressView().controlSize(.small)
                    } else {
                        Label("Refresh", systemImage: "arrow.clockwise")
                    }
                }
                .buttonStyle(ScoutGhostButtonStyle())
                .disabled(state.isRefreshing)

                Button {
                    Task { await state.scanEverything() }
                } label: {
                    Label("Update all", systemImage: "arrow.triangle.2.circlepath")
                }
                .buttonStyle(ScoutGhostButtonStyle())
                .keyboardShortcut("r", modifiers: .command)
            }
        }
        .padding(.horizontal, Theme.pagePadding)
        .padding(.top, 12)
    }

    private var brand: some View {
        HStack(spacing: 10) {
            Text("N")
                .font(.system(size: 15, weight: .heavy))
                .foregroundColor(.white)
                .frame(width: 30, height: 30)
                .background(
                    RoundedRectangle(cornerRadius: 9, style: .continuous)
                        .fill(Theme.accentGradient)
                )
            Text("NexusCorp")
                .font(.system(size: 18, weight: .heavy))
                .tracking(-0.3)
                .foregroundColor(Theme.ink)
        }
    }

    private var modePill: some View {
        Text(state.isLive ? "LIVE" : "SIMULATION")
            .font(.system(size: 11, weight: .heavy))
            .tracking(0.6)
            .foregroundColor(state.isLive ? Theme.green : Theme.violetLt)
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .background(
                Capsule(style: .continuous)
                    .fill((state.isLive ? Theme.green : Theme.violetLt).opacity(0.12))
            )
    }

    // MARK: - Stats band

    private var statBand: some View {
        StatBand {
            ViewThatFits(in: .horizontal) {
                HStack(alignment: .top, spacing: 22) { heroStats }
                VStack(alignment: .leading, spacing: 18) { heroStats }
            }
        }
    }

    @ViewBuilder
    private var heroStats: some View {
        HeroStat(
            "Total value",
            value: Formatters.usd(state.wallet?.nav_usd),
            caption: "\(Formatters.usd(state.wallet?.cash_usd)) ready to spend"
        )
        HeroStat(
            "Open P&L",
            value: signedUsd(state.trade?.unrealized_pnl_usd),
            caption: "\(state.trade?.open_positions ?? 0) open positions"
        )
        HeroStat(
            "Best yield",
            value: Formatters.pct(currentApy),
            caption: currentPool
        )
        HeroStat(
            "Copying",
            value: "\(state.copyStatus?.open_positions ?? 0)",
            caption: "\(state.followedWallets.count) wallets watched"
        )
    }

    // MARK: - Helpers

    private var currentApy: Double? {
        state.yieldStatus?.position?.apy ?? state.yieldStatus?.best?.apy
    }

    private var currentPool: String {
        state.yieldStatus?.position?.project ?? state.yieldStatus?.best?.project ?? "no pool yet"
    }

    private func signedUsd(_ value: Double?) -> String {
        guard let value else { return Formatters.usd(nil) }
        return (value >= 0 ? "+" : "") + Formatters.usd(value)
    }
}

/// Type-erased button style, so a control can switch between primary and ghost
/// styling without duplicating its label.
public struct AnyButtonStyle: ButtonStyle {
    private let makeBodyClosure: (Configuration) -> AnyView

    public init<S: ButtonStyle>(_ style: S) {
        self.makeBodyClosure = { configuration in
            AnyView(style.makeBody(configuration: configuration))
        }
    }

    public func makeBody(configuration: Configuration) -> some View {
        makeBodyClosure(configuration)
    }
}
