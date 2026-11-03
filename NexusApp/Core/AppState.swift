import Foundation
import Combine
import SwiftUI
import NexusCore

@MainActor
public final class AppState: ObservableObject {
    public let client: NexusAPIClient
    public let backendManager: BackendManager

    // Desks Data
    @Published public var health: SystemHealth? = nil
    @Published public var wallet: WalletStatus? = nil
    @Published public var yieldStatus: YieldStatus? = nil
    @Published public var yieldStands: [YieldPool] = []
    @Published public var yieldPlan: YieldPlan? = nil
    @Published public var trade: TradeStatus? = nil
    @Published public var markets: [MarketItem] = []
    @Published public var selectedMarket: MarketItem? = nil
    @Published public var copyStatus: CopyStatus? = nil
    @Published public var followedWallets: [String: FollowedWallet] = [:]
    @Published public var filters: [String: Double] = [:]

    // Activity & Logs
    @Published public var eventLogs: [String] = []
    @Published public var isRefreshing: Bool = false
    @Published public var statusNotice: String? = nil

    private var autoRefreshTimer: Timer?

    public init(baseURL: URL = URL(string: "http://127.0.0.1:8000")!) {
        self.client = NexusAPIClient(baseURL: baseURL)
        self.backendManager = BackendManager()
        log("NexusCorp Terminal initialized.")
        startAutoRefresh()
    }

    deinit {
        autoRefreshTimer?.invalidate()
    }

    public func log(_ message: String) {
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm:ss"
        let timestamp = formatter.string(from: Date())
        let entry = "[\(timestamp)] \(message)"
        eventLogs.insert(entry, at: 0)
        if eventLogs.count > 100 {
            eventLogs.removeLast()
        }
    }

    /// True only when the backend reports live mode. Everything else is a
    /// simulation, and the UI says so in plain words rather than colour alone.
    public var isLive: Bool {
        (health?.mode ?? "paper") == "live"
    }

    /// Refresh, then ask every desk to re-scan. One button, in the order the
    /// desks depend on each other.
    public func scanEverything() async {
        await runYieldTick()
        await triggerFinderScan()
        await triggerCopyScan()
        await markTrades()
    }

    public var copyPositions: [Position] {
        (copyStatus?.positions ?? [:]).map { _, pos in
            var tagged = pos
            tagged.desk = tagged.desk ?? "copy"
            return tagged
        }
    }

    public func startAutoRefresh() {
        autoRefreshTimer?.invalidate()
        autoRefreshTimer = Timer.scheduledTimer(withTimeInterval: 12.0, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                await self?.refreshAll(silent: true)
            }
        }
    }

    public func bootstrap() async {
        log("Connecting to the local NexusCorp API.")
        for attempt in 0..<10 {
            backendManager.checkHealth()
            try? await Task.sleep(nanoseconds: 400_000_000)
            if backendManager.isRunning {
                break
            }
            if attempt == 1 {
                log("API is offline. Starting the Python backend.")
                backendManager.startBackend()
            }
        }
        await refreshAll()
    }

    public func refreshAll(silent: Bool = false) async {
        if !silent { isRefreshing = true }
        defer { if !silent { isRefreshing = false } }

        async let healthRes = load("health") { try await client.health() }
        async let walletRes = load("wallet") { try await client.fetchWallet() }
        async let yieldRes = load("yield") { try await client.fetchYieldStatus() }
        async let standsRes = load("stands") { try await client.fetchYieldStands() }
        async let planRes = load("yield plan") { try await client.fetchYieldPlan() }
        async let tradeRes = load("trade") { try await client.fetchTradeStatus() }
        async let marketsRes = load("markets") { try await client.fetchMarkets(limit: 30) }
        async let copyRes = load("copy") { try await client.fetchCopyStatus() }
        async let walletsRes = load("copy wallets") { try await client.fetchFollowedWallets() }
        async let filtersRes = load("filters") { try await client.fetchFinderFilters() }

        let loaded = await (
            healthRes, walletRes, yieldRes, standsRes, planRes,
            tradeRes, marketsRes, copyRes, walletsRes, filtersRes
        )

        if let value = loaded.0 { health = value }
        if let value = loaded.1 { wallet = value }
        if let value = loaded.2 { yieldStatus = value }
        if let value = loaded.3 { yieldStands = value.allowed ?? [] }
        if let value = loaded.4 { yieldPlan = value }
        if let value = loaded.5 { trade = value }
        if let value = loaded.6 {
            markets = value
            if selectedMarket == nil {
                selectedMarket = value.first
            }
        }
        if let value = loaded.7 { copyStatus = value }
        if let value = loaded.8 { followedWallets = value }
        if let value = loaded.9 { filters = value }

        if !silent {
            if health != nil {
                log("Desks refreshed. Mode \(health?.mode ?? "paper").")
            } else {
                log("API still unreachable on 127.0.0.1:8000.")
            }
        }
    }

    private func load<T>(_ label: String, _ work: () async throws -> T) async -> T? {
        do {
            return try await work()
        } catch {
            log("\(label) failed: \(error.localizedDescription)")
            return nil
        }
    }

    public func selectMarket(_ item: MarketItem) {
        self.selectedMarket = item
        log("Selected market: \(item.symbol ?? item.mint)")
    }

    public func quoteMarket(query: String) async {
        guard !query.trimmingCharacters(in: .whitespaces).isEmpty else { return }
        do {
            let quote = try await client.quote(query: query)
            self.selectedMarket = quote
            // Add or update in markets list
            if let index = markets.firstIndex(where: { $0.mint == quote.mint }) {
                markets[index] = quote
            } else {
                markets.insert(quote, at: 0)
            }
            log("Quoted \(quote.symbol ?? quote.mint): \(Formatters.usd(quote.price_usd))")
        } catch {
            log("Quote error: \(error.localizedDescription)")
        }
    }

    public func executeBuy(
        amountUsd: Double,
        stopLossPct: Double? = nil,
        takeProfitPct: Double? = nil
    ) async {
        guard let mint = selectedMarket?.mint else {
            log("Error: No market selected for buy.")
            return
        }
        do {
            log("Submitting BUY: $\(amountUsd) for \(selectedMarket?.symbol ?? mint)...")
            let updatedTrade = try await client.buy(
                mint: mint,
                amountUsd: amountUsd,
                stopLossPct: stopLossPct,
                takeProfitPct: takeProfitPct
            )
            self.trade = updatedTrade
            log("BUY executed successfully! Open positions: \(updatedTrade.open_positions ?? 0)")
            await refreshAll(silent: true)
        } catch {
            log("BUY failed: \(error.localizedDescription)")
        }
    }

    public func executeSell(amountUsd: Double? = nil) async {
        guard let mint = selectedMarket?.mint else {
            log("Error: No market selected for sell.")
            return
        }
        do {
            log("Submitting SELL for \(selectedMarket?.symbol ?? mint)...")
            let updatedTrade = try await client.sell(mint: mint, amountUsd: amountUsd)
            self.trade = updatedTrade
            log("SELL executed successfully!")
            await refreshAll(silent: true)
        } catch {
            log("SELL failed: \(error.localizedDescription)")
        }
    }

    public func closePosition(desk: String, mint: String) async {
        do {
            if desk == "copy" {
                _ = try await client.closeCopyPosition(mint: mint)
            } else {
                _ = try await client.sell(mint: mint, amountUsd: nil)
            }
            log("Closed \(desk) position for \(Formatters.shortAddress(mint, size: 4))")
            await refreshAll(silent: true)
        } catch {
            log("Close position failed: \(error.localizedDescription)")
        }
    }

    public func markTrades() async {
        do {
            let updated = try await client.markTrades()
            self.trade = updated
            log("Marked open positions against live market.")
        } catch {
            log("Mark error: \(error.localizedDescription)")
        }
    }

    public func runYieldTick() async {
        do {
            log("Triggering yield rebalance tick...")
            let updated = try await client.runYieldTick()
            self.yieldStatus = updated
            log("Yield tick complete: \(updated.last_action ?? "checked")")
            await refreshAll(silent: true)
        } catch {
            log("Yield tick failed: \(error.localizedDescription)")
        }
    }

    public func depositHub(amount: Double, note: String) async {
        do {
            let updated = try await client.receive(amount: amount, note: note)
            self.wallet = updated
            log("Received \(Formatters.usd(amount)) into Hub wallet.")
        } catch {
            log("Deposit failed: \(error.localizedDescription)")
        }
    }

    public func sendHub(amount: Double, dest: String, note: String) async {
        do {
            let updated = try await client.send(amount: amount, dest: dest, note: note)
            self.wallet = updated
            log("Transferred \(Formatters.usd(amount)) to \(dest).")
        } catch {
            log("Send failed: \(error.localizedDescription)")
        }
    }

    public func withdrawHub(amount: Double, source: String) async {
        do {
            let updated = try await client.withdraw(amount: amount, source: source)
            self.wallet = updated
            log("Withdrew \(Formatters.usd(amount)) from \(source) to Hub.")
        } catch {
            log("Withdraw failed: \(error.localizedDescription)")
        }
    }

    public func followWallet(address: String, label: String) async {
        do {
            _ = try await client.followWallet(address: address, label: label)
            log("Followed wallet: \(Formatters.shortAddress(address, size: 6)) (\(label))")
            let fw = try await client.fetchFollowedWallets()
            self.followedWallets = fw
        } catch {
            log("Follow wallet failed: \(error.localizedDescription)")
        }
    }

    public func unfollowWallet(address: String) async {
        do {
            _ = try await client.unfollowWallet(address: address)
            log("Unfollowed wallet: \(Formatters.shortAddress(address, size: 6))")
            let fw = try await client.fetchFollowedWallets()
            self.followedWallets = fw
        } catch {
            log("Unfollow failed: \(error.localizedDescription)")
        }
    }

    public func triggerCopyScan() async {
        do {
            log("Triggering Copy Trader scan...")
            _ = try await client.triggerCopyScan()
            log("Copy scan completed.")
            await refreshAll(silent: true)
        } catch {
            log("Copy scan error: \(error.localizedDescription)")
        }
    }

    public func triggerFinderScan() async {
        do {
            log("Scanning token markets via Finder desk...")
            _ = try await client.scanFinder()
            let m = try await client.fetchMarkets(limit: 30)
            self.markets = m
            log("Finder scan complete. Loaded \(m.count) markets.")
        } catch {
            log("Finder scan error: \(error.localizedDescription)")
        }
    }

    public func applyFinderPreset(_ name: String) async {
        do {
            let applied = try await client.applyFinderPreset(name)
            self.filters = applied
            log("Finder preset \(name) applied.")
            await triggerFinderScan()
        } catch {
            log("Preset failed: \(error.localizedDescription)")
        }
    }

    public func freezeAll() async {
        do {
            _ = try await client.freeze(desk: "all", reason: "Native HUD Master Switch")
            log("KILLSWITCH ENGAGED: All desks FROZEN.")
            await refreshAll(silent: true)
        } catch {
            log("Freeze failed: \(error.localizedDescription)")
        }
    }

    public func thawAll() async {
        do {
            _ = try await client.thaw(desk: "all")
            log("SYSTEM THAWED: All desks normal.")
            await refreshAll(silent: true)
        } catch {
            log("Thaw failed: \(error.localizedDescription)")
        }
    }

    public func freezeDesk(_ desk: String) async {
        do {
            _ = try await client.freeze(desk: desk, reason: "Manual toggle")
            log("Froze desk: \(desk)")
            await refreshAll(silent: true)
        } catch {
            log("Freeze desk error: \(error.localizedDescription)")
        }
    }

    public func thawDesk(_ desk: String) async {
        do {
            _ = try await client.thaw(desk: desk)
            log("Thawed desk: \(desk)")
            await refreshAll(silent: true)
        } catch {
            log("Thaw desk error: \(error.localizedDescription)")
        }
    }
}
