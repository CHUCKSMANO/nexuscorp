import NexusCore
import SwiftUI

/// Trade: find a token, look at it, decide whether to buy.
public struct TradeDeskView: View {
    @ObservedObject var state: AppState

    @State private var quoteQuery: String = ""
    @State private var orderSide: String = "buy"
    @State private var orderAmount: String = "25.00"
    @State private var stopLossPct: String = "10.0"
    @State private var takeProfitPct: String = "25.0"
    @State private var isSubmitting: Bool = false

    private var side: String { orderSide }

    public var body: some View {
        VStack(spacing: 0) {
            DeskHeader(
                "Trade",
                title: "Buy and sell tokens.",
                subtitle: "Search any Solana token, read its live price, and place a simulated order."
            )
            .padding(.horizontal, Theme.pagePadding)
            .padding(.top, 22)
            .padding(.bottom, 16)

            HSplitView {
                tokenList
                detail
            }
        }
    }

    // MARK: - Left: which token

    private var tokenList: some View {
        VStack(alignment: .leading, spacing: Theme.gap) {
            Panel("Find a token", subtitle: "Search by name, or scan for the best opportunities.") {
                TextField("Token name or contract", text: $quoteQuery)
                    .scoutField()
                    .onSubmit { quote() }
                HStack {
                    Button("Look up") { quote() }
                        .buttonStyle(ScoutPrimaryButtonStyle())
                    Spacer()
                    Button {
                        Task { await state.triggerFinderScan() }
                    } label: {
                        Label("Scan", systemImage: "sparkle.magnifyingglass")
                    }
                    .buttonStyle(ScoutGhostButtonStyle())
                }
            }

            Panel("Suggestions") {
                RowList(
                    count: state.markets.count,
                    empty: {
                        EmptyState(
                            icon: "magnifyingglass",
                            title: "No tokens found",
                            message: "Press Scan to look for tokens, or search above."
                        )
                    }
                ) {
                    ForEach(state.markets) { item in
                        tokenRow(item)
                    }
                }
            }

            Spacer(minLength: 0)
        }
        .padding(Theme.pagePadding)
        .frame(minWidth: 300, idealWidth: 330)
        .background(Theme.bg)
    }

    private func tokenRow(_ item: MarketItem) -> some View {
        let isSelected = state.selectedMarket?.mint == item.mint
        let change = item.price_change_24h ?? 0.0

        return Button {
            state.selectMarket(item)
        } label: {
            HStack(spacing: 8) {
                VStack(alignment: .leading, spacing: 1) {
                    Text(item.symbol ?? Formatters.shortAddress(item.mint, size: 3))
                        .font(.system(size: 13, weight: .medium))
                        .foregroundColor(Theme.ink)
                    Text(item.dex ?? "")
                        .font(Theme.caption)
                        .foregroundColor(Theme.dim)
                }
                Spacer(minLength: 4)
                VStack(alignment: .trailing, spacing: 1) {
                    Text(Formatters.px(item.price_usd))
                        .font(Theme.bodyNumber)
                        .foregroundColor(Theme.ink)
                    Text(signedPct(change))
                        .font(Theme.captionNumber)
                        .foregroundColor(Theme.pnl(change))
                }
            }
            .padding(.vertical, 7)
            .padding(.horizontal, 8)
            .contentShape(Rectangle())
            .background(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .fill(isSelected ? Theme.violet.opacity(0.14) : .clear)
            )
        }
        .buttonStyle(.plain)
    }

    // MARK: - Right: this token

    private var detail: some View {
        VSplitView {
            VStack(alignment: .leading, spacing: Theme.gap) {
                if let market = state.selectedMarket {
                    tokenHeader(market)
                    chart
                } else {
                    EmptyState(
                        icon: "chart.line.uptrend.xyaxis",
                        title: "Pick a token",
                        message: "Choose one from the list to see its price and place an order."
                    )
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            }
            .padding(Theme.pagePadding)
            .frame(minHeight: 300)
            .background(Theme.bg)

            openPositions
        }
    }

    private func tokenHeader(_ market: MarketItem) -> some View {
        let change = market.price_change_24h ?? 0.0
        return VStack(alignment: .leading, spacing: Theme.gap) {
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Text(market.symbol ?? "Token")
                    .font(.system(size: 22, weight: .bold))
                    .foregroundColor(Theme.ink)
                Text(signedPct(change) + " in 24 hours")
                    .font(Theme.body)
                    .foregroundColor(Theme.pnl(change))
                Spacer()
            }

            StatRow([
                StatTile("Price", value: Formatters.px(market.price_usd)),
                StatTile("Liquidity", value: Formatters.usd(market.liquidity_usd), caption: "available to trade"),
                StatTile("24h volume", value: Formatters.usd(market.volume_24h)),
                StatTile("Market cap", value: Formatters.usd(market.market_cap ?? market.fdv))
            ])

            orderForm
        }
    }

    private var chart: some View {
        TokenChartView(urlString: state.selectedMarket?.chart_url)
            .frame(maxWidth: .infinity, minHeight: 240, maxHeight: .infinity)
            .clipShape(RoundedRectangle(cornerRadius: Theme.cardRadius, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: Theme.cardRadius, style: .continuous)
                    .stroke(Theme.line, lineWidth: 1)
            )
    }

    // MARK: - Order form

    private var orderForm: some View {
        VStack(alignment: .leading, spacing: Theme.gap) {
            HStack(spacing: 8) {
                Picker("", selection: $orderSide) {
                    Text("Buy").tag("buy")
                    Text("Sell").tag("sell")
                }
                .pickerStyle(.segmented)
                .labelsHidden()
                .tint(Theme.violet)
                .frame(width: 170)

                Spacer()

                if !state.isLive {
                    Tag("Simulation", color: Theme.violetLt)
                }
            }

            HStack(spacing: 8) {
                TextField("Amount in dollars", text: $orderAmount)
                    .scoutField()
                    .frame(width: 130)
                ForEach(["10", "25", "50", "100"], id: \.self) { value in
                    Button("$\(value)") { orderAmount = "\(value).00" }
                        .buttonStyle(ScoutGhostButtonStyle())
                        .controlSize(.small)
                }
            }

            if side == "buy" {
                HStack(spacing: 8) {
                    labelledField("Sell if it drops %", text: $stopLossPct)
                    labelledField("Sell if it rises %", text: $takeProfitPct)
                }
            }

            Button(action: submit) {
                Text(isSubmitting
                     ? "Working..."
                     : (side == "buy" ? "Buy" : "Sell"))
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(side == "buy" ? AnyButtonStyle(ScoutPrimaryButtonStyle()) : AnyButtonStyle(ScoutDangerButtonStyle()))
            .disabled(state.selectedMarket == nil || isSubmitting)
        }
        .card()
    }

    private func labelledField(_ label: String, text: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(Theme.caption)
                .foregroundColor(Theme.muted)
            TextField("", text: text)
                .scoutField()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: - Open positions

    private var openPositions: some View {
        VStack(alignment: .leading, spacing: Theme.gap) {
            Panel("Your open trades", subtitle: "Marked to the current price.") {
                RowList(
                    count: state.trade?.positions?.count ?? 0,
                    empty: {
                        EmptyState(icon: "tray", title: "No open trades")
                    }
                ) {
                    ForEach(state.trade?.positions ?? []) { pos in
                        TableRow {
                            Text(pos.symbol ?? Formatters.shortAddress(pos.mint))
                                .font(.system(size: 13, weight: .medium))
                                .foregroundColor(Theme.ink)
                        } trailing: {
                            HStack(spacing: 10) {
                                Text(Formatters.usd(pos.mark_usd ?? pos.cost_usd))
                                    .font(Theme.bodyNumber)
                                    .foregroundColor(Theme.ink)
                                Text(signedUsd(pos.unrealized_pnl_usd))
                                    .font(Theme.bodyNumber)
                                    .foregroundColor(Theme.pnl(pos.unrealized_pnl_usd ?? 0))
                                    .frame(width: 78, alignment: .trailing)
                                Button("Sell") {
                                    Task { await state.closePosition(desk: "trade", mint: pos.mint) }
                                }
                                .buttonStyle(ScoutGhostButtonStyle())
                                .controlSize(.small)
                            }
                        }
                    }
                }
            }

            Panel("Recent trades") {
                fillsList(state.trade?.fills ?? [], emptyTitle: "No trades yet")
            }
        }
        .padding(Theme.pagePadding)
        .frame(minHeight: 180)
        .background(Theme.bg)
    }

    // MARK: - Actions

    private func quote() {
        let query = quoteQuery.trimmingCharacters(in: .whitespaces)
        guard !query.isEmpty else { return }
        Task {
            await state.quoteMarket(query: query)
            quoteQuery = ""
        }
    }

    private func submit() {
        isSubmitting = true
        Task {
            let amount = Double(orderAmount) ?? 25.0
            if side == "buy" {
                await state.executeBuy(
                    amountUsd: amount,
                    stopLossPct: Double(stopLossPct),
                    takeProfitPct: Double(takeProfitPct)
                )
            } else {
                await state.executeSell(amountUsd: amount)
            }
            isSubmitting = false
        }
    }

    private func signedUsd(_ value: Double?) -> String {
        guard let value else { return "--" }
        return (value >= 0 ? "+" : "") + Formatters.usd(value)
    }

    private func signedPct(_ value: Double) -> String {
        (value >= 0 ? "+" : "") + Formatters.pct(value)
    }
}
