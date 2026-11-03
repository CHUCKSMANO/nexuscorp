import Foundation

// MARK: - Health / runtime

public struct ChainInfo: Codable, Equatable {
    public let pubkey: String?
    public let devnet_sol: Double?
    public let devnet_usdc: Double?
    public let mainnet_sol: Double?
    public let mainnet_usdc: Double?

    public init(
        pubkey: String? = nil,
        devnet_sol: Double? = nil,
        devnet_usdc: Double? = nil,
        mainnet_sol: Double? = nil,
        mainnet_usdc: Double? = nil
    ) {
        self.pubkey = pubkey
        self.devnet_sol = devnet_sol
        self.devnet_usdc = devnet_usdc
        self.mainnet_sol = mainnet_sol
        self.mainnet_usdc = mainnet_usdc
    }
}

public struct DeskAllocation: Codable, Equatable {
    public let idle_usd: Double?
    public let deployed_usd: Double?
    public let total_usd: Double?

    public init(idle_usd: Double? = 0, deployed_usd: Double? = 0, total_usd: Double? = 0) {
        self.idle_usd = idle_usd
        self.deployed_usd = deployed_usd
        self.total_usd = total_usd
    }
}

public struct LedgerEntry: Codable, Identifiable, Equatable {
    public var id: String { "\(ts ?? "")_\(kind ?? "")_\(amount_usd ?? 0)_\(from ?? "")_\(to ?? "")" }
    public let ts: String?
    public let kind: String?
    public let amount_usd: Double?
    public let from: String?
    public let to: String?
    public let note: String?

    public init(
        ts: String? = nil,
        kind: String? = nil,
        amount_usd: Double? = nil,
        from: String? = nil,
        to: String? = nil,
        note: String? = nil
    ) {
        self.ts = ts
        self.kind = kind
        self.amount_usd = amount_usd
        self.from = from
        self.to = to
        self.note = note
    }
}

public struct WalletStatus: Codable, Equatable {
    public let desk: String?
    public let mode: String?
    public let live_enabled: Bool?
    public let receive_address: String?
    public let cash_usd: Double?
    public let nav_usd: Double?
    public let idle_usd: Double?
    public let deployed_usd: Double?
    public let desks: [String: DeskAllocation]?
    public let chain: ChainInfo?
    public let ledger: [LedgerEntry]?

    public init(
        desk: String? = "wallet",
        mode: String? = "paper",
        live_enabled: Bool? = false,
        receive_address: String? = nil,
        cash_usd: Double? = 0.0,
        nav_usd: Double? = 0.0,
        idle_usd: Double? = 0.0,
        deployed_usd: Double? = 0.0,
        desks: [String: DeskAllocation]? = nil,
        chain: ChainInfo? = nil,
        ledger: [LedgerEntry]? = nil
    ) {
        self.desk = desk
        self.mode = mode
        self.live_enabled = live_enabled
        self.receive_address = receive_address
        self.cash_usd = cash_usd
        self.nav_usd = nav_usd
        self.idle_usd = idle_usd
        self.deployed_usd = deployed_usd
        self.desks = desks
        self.chain = chain
        self.ledger = ledger
    }
}

// MARK: - Yield

public struct YieldPosition: Codable, Equatable {
    public let project: String?
    public let amount_usd: Double?
    public let apy: Double?
    public let pool_id: String?

    public init(project: String? = nil, amount_usd: Double? = nil, apy: Double? = nil, pool_id: String? = nil) {
        self.project = project
        self.amount_usd = amount_usd
        self.apy = apy
        self.pool_id = pool_id
    }
}

public struct YieldPool: Codable, Identifiable, Equatable {
    public var id: String { "\(pool_id ?? "")|\(project ?? "")|\(symbol ?? "")|\(tvl_usd ?? 0)" }
    public let project: String?
    public let symbol: String?
    public let apy: Double?
    public let tvl_usd: Double?
    public let pool_id: String?
    public let source: String?

    public init(
        project: String? = nil,
        symbol: String? = nil,
        apy: Double? = nil,
        tvl_usd: Double? = nil,
        pool_id: String? = nil,
        source: String? = nil
    ) {
        self.project = project
        self.symbol = symbol
        self.apy = apy
        self.tvl_usd = tvl_usd
        self.pool_id = pool_id
        self.source = source
    }
}

public struct YieldStatus: Codable, Equatable {
    public let desk: String?
    public let mode: String?
    public let frozen: Bool?
    public let wallet: String?
    public let cash_usd: Double?
    public let position: YieldPosition?
    public let paper_per_day: Double?
    public let lifetime_earned_usd: Double?
    public let best: YieldPool?
    public let source: String?
    public let last_action: String?
    public let last_reason: String?

    public init(
        desk: String? = "yield",
        mode: String? = "paper",
        frozen: Bool? = false,
        wallet: String? = nil,
        cash_usd: Double? = 0.0,
        position: YieldPosition? = nil,
        paper_per_day: Double? = 0.0,
        lifetime_earned_usd: Double? = 0.0,
        best: YieldPool? = nil,
        source: String? = nil,
        last_action: String? = nil,
        last_reason: String? = nil
    ) {
        self.desk = desk
        self.mode = mode
        self.frozen = frozen
        self.wallet = wallet
        self.cash_usd = cash_usd
        self.position = position
        self.paper_per_day = paper_per_day
        self.lifetime_earned_usd = lifetime_earned_usd
        self.best = best
        self.source = source
        self.last_action = last_action
        self.last_reason = last_reason
    }
}

public struct YieldStandsResponse: Codable, Equatable {
    public let source: String?
    public let count: Int?
    public let best: YieldPool?
    public let allowed: [YieldPool]?

    public init(source: String? = nil, count: Int? = nil, best: YieldPool? = nil, allowed: [YieldPool]? = nil) {
        self.source = source
        self.count = count
        self.best = best
        self.allowed = allowed
    }
}

public struct YieldPlanDest: Codable, Equatable {
    public let project: String?
    public let apy: Double?
    public let tvl_usd: Double?
    public let pool_id: String?

    public init(project: String? = nil, apy: Double? = nil, tvl_usd: Double? = nil, pool_id: String? = nil) {
        self.project = project
        self.apy = apy
        self.tvl_usd = tvl_usd
        self.pool_id = pool_id
    }
}

public struct YieldPlan: Codable, Equatable {
    public let wallet: String?
    public let sol: Double?
    public let usdc: Double?
    public let amount_usd: Double?
    public let dest: YieldPlanDest?
    public let would_send: Bool?
    public let blockers: [String]?

    public init(
        wallet: String? = nil,
        sol: Double? = nil,
        usdc: Double? = nil,
        amount_usd: Double? = nil,
        dest: YieldPlanDest? = nil,
        would_send: Bool? = false,
        blockers: [String]? = []
    ) {
        self.wallet = wallet
        self.sol = sol
        self.usdc = usdc
        self.amount_usd = amount_usd
        self.dest = dest
        self.would_send = would_send
        self.blockers = blockers
    }
}

// MARK: - Runtime / health

public struct RuntimeInfo: Codable, Equatable {
    public let started_at: String?
    public let last_yield_tick_at: String?
    public let last_finder_scan_at: String?
    public let last_copy_scan_at: String?

    public init(
        started_at: String? = nil,
        last_yield_tick_at: String? = nil,
        last_finder_scan_at: String? = nil,
        last_copy_scan_at: String? = nil
    ) {
        self.started_at = started_at
        self.last_yield_tick_at = last_yield_tick_at
        self.last_finder_scan_at = last_finder_scan_at
        self.last_copy_scan_at = last_copy_scan_at
    }
}

public struct FrozenState: Codable, Equatable {
    public let all: Bool
    public let yield: Bool
    public let finder: Bool
    public let copy: Bool
    public let reason: String?

    public init(all: Bool = false, yield: Bool = false, finder: Bool = false, copy: Bool = false, reason: String? = nil) {
        self.all = all
        self.yield = yield
        self.finder = finder
        self.copy = copy
        self.reason = reason
    }
}

public struct SystemHealth: Codable, Equatable {
    public let ok: Bool
    public let name: String
    public let mode: String
    public let finder_execution: String?
    public let copy_execution: String?
    public let frozen: FrozenState
    public let runtime: RuntimeInfo?

    public init(
        ok: Bool = false,
        name: String = "The Token Yielder",
        mode: String = "paper",
        finder_execution: String? = nil,
        copy_execution: String? = nil,
        frozen: FrozenState = FrozenState(),
        runtime: RuntimeInfo? = nil
    ) {
        self.ok = ok
        self.name = name
        self.mode = mode
        self.finder_execution = finder_execution
        self.copy_execution = copy_execution
        self.frozen = frozen
        self.runtime = runtime
    }
}

public struct FinderStatus: Codable, Equatable {
    public let desk: String?
    public let tracked_count: Int?
    public let last_scan_at: String?

    public init(desk: String? = "finder", tracked_count: Int? = 0, last_scan_at: String? = nil) {
        self.desk = desk
        self.tracked_count = tracked_count
        self.last_scan_at = last_scan_at
    }
}

// MARK: - Copy trading

public struct FollowedWallet: Codable, Equatable {
    public let label: String?
    public let added_at: String?
    public let bootstrapped: Bool?
    public let last_signature: String?
    public let last_scan_at: String?

    public init(
        label: String? = nil,
        added_at: String? = nil,
        bootstrapped: Bool? = false,
        last_signature: String? = nil,
        last_scan_at: String? = nil
    ) {
        self.label = label
        self.added_at = added_at
        self.bootstrapped = bootstrapped
        self.last_signature = last_signature
        self.last_scan_at = last_scan_at
    }
}

public struct WalletsResponse: Codable, Equatable {
    public let wallets: [String: FollowedWallet]

    public init(wallets: [String: FollowedWallet] = [:]) {
        self.wallets = wallets
    }
}

public struct CopyStatus: Codable, Equatable {
    public let desk: String?
    public let wallet_count: Int?
    public let wallets: [String: FollowedWallet]?
    public let open_positions: Int?
    public let positions: [String: Position]?
    public let recent_fills: [Fill]?
    public let cash_usd: Double?

    public init(
        desk: String? = "copy",
        wallet_count: Int? = 0,
        wallets: [String: FollowedWallet]? = nil,
        open_positions: Int? = 0,
        positions: [String: Position]? = nil,
        recent_fills: [Fill]? = nil,
        cash_usd: Double? = 0.0
    ) {
        self.desk = desk
        self.wallet_count = wallet_count
        self.wallets = wallets
        self.open_positions = open_positions
        self.positions = positions
        self.recent_fills = recent_fills
        self.cash_usd = cash_usd
    }
}

// MARK: - Trade

public struct Position: Codable, Identifiable, Equatable {
    public var id: String { mint }
    public let mint: String
    public var symbol: String?
    public var desk: String?
    public var amount: Double?
    public var cost_usd: Double?
    public var entry_price: Double?
    public var mark_price: Double?
    public var mark_usd: Double?
    public var unrealized_pnl_usd: Double?
    public var stop_price: Double?
    public var take_price: Double?

    public init(
        mint: String,
        symbol: String? = nil,
        desk: String? = nil,
        amount: Double? = nil,
        cost_usd: Double? = nil,
        entry_price: Double? = nil,
        mark_price: Double? = nil,
        mark_usd: Double? = nil,
        unrealized_pnl_usd: Double? = nil,
        stop_price: Double? = nil,
        take_price: Double? = nil
    ) {
        self.mint = mint
        self.symbol = symbol
        self.desk = desk
        self.amount = amount
        self.cost_usd = cost_usd
        self.entry_price = entry_price
        self.mark_price = mark_price
        self.mark_usd = mark_usd
        self.unrealized_pnl_usd = unrealized_pnl_usd
        self.stop_price = stop_price
        self.take_price = take_price
    }
}

public struct Fill: Codable, Identifiable, Equatable {
    public var id: String { "\(ts ?? "")_\(side ?? "")_\(mint ?? "")_\(usd ?? 0)" }
    public let ts: String?
    public let side: String?
    public let symbol: String?
    public let mint: String?
    public let usd: Double?
    public let cost_usd: Double?
    public let proceeds_usd: Double?
    public let price: Double?
    public let entry_price: Double?
    public let reason: String?
    public let dex: String?
    public let desk: String?

    public var effectivePrice: Double { price ?? entry_price ?? 0 }
    public var effectiveUsd: Double { usd ?? cost_usd ?? proceeds_usd ?? 0 }

    public init(
        ts: String? = nil,
        side: String? = nil,
        symbol: String? = nil,
        mint: String? = nil,
        usd: Double? = nil,
        cost_usd: Double? = nil,
        proceeds_usd: Double? = nil,
        price: Double? = nil,
        entry_price: Double? = nil,
        reason: String? = nil,
        dex: String? = nil,
        desk: String? = nil
    ) {
        self.ts = ts
        self.side = side
        self.symbol = symbol
        self.mint = mint
        self.usd = usd
        self.cost_usd = cost_usd
        self.proceeds_usd = proceeds_usd
        self.price = price
        self.entry_price = entry_price
        self.reason = reason
        self.dex = dex
        self.desk = desk
    }
}

public struct TradeStatus: Codable, Equatable {
    public let desk: String?
    public let mode: String?
    public let live_enabled: Bool?
    public let frozen: Bool?
    public let cash_usd: Double?
    public let open_mark_usd: Double?
    public let unrealized_pnl_usd: Double?
    public let realized_pnl_usd: Double?
    public let equity_usd: Double?
    public let open_positions: Int?
    public let positions: [Position]?
    public let fills: [Fill]?
    public let tracked_count: Int?
    public let max_trade_usd: Double?

    public init(
        desk: String? = "trade",
        mode: String? = "paper",
        live_enabled: Bool? = false,
        frozen: Bool? = false,
        cash_usd: Double? = 0.0,
        open_mark_usd: Double? = 0.0,
        unrealized_pnl_usd: Double? = 0.0,
        realized_pnl_usd: Double? = 0.0,
        equity_usd: Double? = 0.0,
        open_positions: Int? = 0,
        positions: [Position]? = nil,
        fills: [Fill]? = nil,
        tracked_count: Int? = 0,
        max_trade_usd: Double? = 0.0
    ) {
        self.desk = desk
        self.mode = mode
        self.live_enabled = live_enabled
        self.frozen = frozen
        self.cash_usd = cash_usd
        self.open_mark_usd = open_mark_usd
        self.unrealized_pnl_usd = unrealized_pnl_usd
        self.realized_pnl_usd = realized_pnl_usd
        self.equity_usd = equity_usd
        self.open_positions = open_positions
        self.positions = positions
        self.fills = fills
        self.tracked_count = tracked_count
        self.max_trade_usd = max_trade_usd
    }
}

public struct MarketItem: Codable, Identifiable, Equatable {
    public var id: String { mint }
    public let mint: String
    public let symbol: String?
    public let name: String?
    public let price_usd: Double?
    public let price_change_5m: Double?
    public let price_change_1h: Double?
    public let price_change_6h: Double?
    public let price_change_24h: Double?
    public let liquidity_usd: Double?
    public let volume_24h: Double?
    public let fdv: Double?
    public let market_cap: Double?
    public let dex: String?
    public let pair_address: String?
    public let pair_url: String?
    public let chart_url: String?

    public init(
        mint: String,
        symbol: String? = nil,
        name: String? = nil,
        price_usd: Double? = nil,
        price_change_5m: Double? = nil,
        price_change_1h: Double? = nil,
        price_change_6h: Double? = nil,
        price_change_24h: Double? = nil,
        liquidity_usd: Double? = nil,
        volume_24h: Double? = nil,
        fdv: Double? = nil,
        market_cap: Double? = nil,
        dex: String? = nil,
        pair_address: String? = nil,
        pair_url: String? = nil,
        chart_url: String? = nil
    ) {
        self.mint = mint
        self.symbol = symbol
        self.name = name
        self.price_usd = price_usd
        self.price_change_5m = price_change_5m
        self.price_change_1h = price_change_1h
        self.price_change_6h = price_change_6h
        self.price_change_24h = price_change_24h
        self.liquidity_usd = liquidity_usd
        self.volume_24h = volume_24h
        self.fdv = fdv
        self.market_cap = market_cap
        self.dex = dex
        self.pair_address = pair_address
        self.pair_url = pair_url
        self.chart_url = chart_url
    }
}

public struct MarketsResponse: Codable, Equatable {
    public let markets: [MarketItem]

    public init(markets: [MarketItem] = []) {
        self.markets = markets
    }
}

// MARK: - Aggregate status

public struct StatusResponse: Codable, Equatable {
    public let frozen: FrozenState?
    public let yield: YieldStatus?
    public let wallet: WalletStatus?
    public let finder: FinderStatus?
    public let copy: CopyStatus?
    public let runtime: RuntimeInfo?

    public init(
        frozen: FrozenState? = nil,
        yield: YieldStatus? = nil,
        wallet: WalletStatus? = nil,
        finder: FinderStatus? = nil,
        copy: CopyStatus? = nil,
        runtime: RuntimeInfo? = nil
    ) {
        self.frozen = frozen
        self.yield = yield
        self.wallet = wallet
        self.finder = finder
        self.copy = copy
        self.runtime = runtime
    }
}

// MARK: - Request bodies

public struct BuyRequest: Codable, Equatable {
    public let mint: String
    public let amount_usd: Double
    public let stop_loss_pct: Double?
    public let take_profit_pct: Double?

    public init(mint: String, amount_usd: Double, stop_loss_pct: Double? = nil, take_profit_pct: Double? = nil) {
        self.mint = mint
        self.amount_usd = amount_usd
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
    }
}

public struct SellRequest: Codable, Equatable {
    public let mint: String
    public let amount_usd: Double?

    public init(mint: String, amount_usd: Double? = nil) {
        self.mint = mint
        self.amount_usd = amount_usd
    }
}

public struct ReceiveRequest: Codable, Equatable {
    public let amount_usd: Double
    public let note: String

    public init(amount_usd: Double, note: String = "") {
        self.amount_usd = amount_usd
        self.note = note
    }
}

public struct SendRequest: Codable, Equatable {
    public let amount_usd: Double
    public let dest: String
    public let note: String

    public init(amount_usd: Double, dest: String, note: String = "") {
        self.amount_usd = amount_usd
        self.dest = dest
        self.note = note
    }
}

public struct WithdrawRequest: Codable, Equatable {
    public let amount_usd: Double
    public let source: String

    public init(amount_usd: Double, source: String) {
        self.amount_usd = amount_usd
        self.source = source
    }
}

public struct FollowRequest: Codable, Equatable {
    public let address: String
    public let label: String

    public init(address: String, label: String = "") {
        self.address = address
        self.label = label
    }
}

// MARK: - Formatters

public enum Formatters {
    public static func usd(_ value: Double?) -> String {
        guard let value = value else { return "$0.00" }
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.currencySymbol = "$"
        formatter.maximumFractionDigits = 2
        formatter.minimumFractionDigits = 2
        return formatter.string(from: NSNumber(value: value)) ?? String(format: "$%.2f", value)
    }

    public static func pct(_ value: Double?) -> String {
        guard let value = value else { return "0.00%" }
        return String(format: "%.2f%%", value)
    }

    public static func px(_ value: Double?) -> String {
        guard let value = value, value > 0 else { return "--" }
        if value >= 1 {
            return String(format: "%.4f", value)
        } else {
            return String(format: "%.6f", value)
        }
    }

    public static func shortAddress(_ address: String?, size: Int = 4) -> String {
        guard let address = address, !address.isEmpty else { return "--" }
        if address.count <= size * 2 { return address }
        let prefix = address.prefix(size)
        let suffix = address.suffix(size)
        return "\(prefix)...\(suffix)"
    }
}
