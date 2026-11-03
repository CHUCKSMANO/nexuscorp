import Foundation

public enum APIError: Error, LocalizedError {
    case invalidURL
    case http(Int, String)
    case decoding(Error)
    case transport(Error)

    public var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid URL"
        case .http(let code, let body):
            return "HTTP \(code): \(body)"
        case .decoding(let error):
            return "Decode failed: \(error.localizedDescription)"
        case .transport(let error):
            return error.localizedDescription
        }
    }
}

/// Talks to the local Python backend on 127.0.0.1:8000.
public final class NexusAPIClient {
    public var baseURL: URL

    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    public init(baseURL: URL) {
        self.baseURL = baseURL
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 20
        config.waitsForConnectivity = false
        self.session = URLSession(configuration: config)
        self.decoder = JSONDecoder()
        self.encoder = JSONEncoder()
    }

    public func updateBaseURL(_ url: URL) {
        self.baseURL = url
    }

    // MARK: - URL building

    public static func makeURL(base: URL, path: String, query: [String: String]? = nil) throws -> URL {
        var url = base
        let components = path.split(separator: "/").map(String.init).filter { !$0.isEmpty }
        for component in components {
            url.appendPathComponent(component)
        }

        guard let query, !query.isEmpty else { return url }
        guard var urlComponents = URLComponents(url: url, resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL
        }
        urlComponents.queryItems = query
            .sorted { $0.key < $1.key }
            .map { URLQueryItem(name: $0.key, value: $0.value) }
        guard let final = urlComponents.url else { throw APIError.invalidURL }
        return final
    }

    // MARK: - Transport

    private func send(
        path: String,
        method: String = "GET",
        query: [String: String]? = nil,
        body: Data? = nil
    ) async throws -> Data {
        let url = try Self.makeURL(base: baseURL, path: path, query: query)
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let body {
            request.httpBody = body
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }

        do {
            let (data, response) = try await session.data(for: request)
            guard let http = response as? HTTPURLResponse else {
                throw APIError.transport(URLError(.badServerResponse))
            }
            guard (200...299).contains(http.statusCode) else {
                let text = String(data: data, encoding: .utf8) ?? ""
                throw APIError.http(http.statusCode, text)
            }
            return data
        } catch let error as APIError {
            throw error
        } catch {
            throw APIError.transport(error)
        }
    }

    private func request<T: Decodable>(
        _ path: String,
        method: String = "GET",
        query: [String: String]? = nil,
        body: Data? = nil
    ) async throws -> T {
        let data = try await send(path: path, method: method, query: query, body: body)
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }

    private func requestObject(
        _ path: String,
        method: String = "GET",
        query: [String: String]? = nil,
        body: Data? = nil
    ) async throws -> [String: Any] {
        let data = try await send(path: path, method: method, query: query, body: body)
        guard let object = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw APIError.decoding(APIError.invalidURL)
        }
        return object
    }

    private func encodeBody<T: Encodable>(_ value: T) throws -> Data {
        do {
            return try encoder.encode(value)
        } catch {
            throw APIError.decoding(error)
        }
    }

    // MARK: - Health / status

    public func health() async throws -> SystemHealth {
        try await request("health")
    }

    public func status() async throws -> StatusResponse {
        try await request("status")
    }

    // MARK: - Yield

    public func fetchYieldStatus() async throws -> YieldStatus {
        try await request("yield/status")
    }

    public func fetchYieldStands() async throws -> YieldStandsResponse {
        try await request("yield/stands")
    }

    public func fetchYieldPlan() async throws -> YieldPlan {
        try await request("yield/plan")
    }

    public func runYieldTick() async throws -> YieldStatus {
        try await request("yield/tick", method: "POST")
    }

    // MARK: - Wallet

    public func fetchWallet() async throws -> WalletStatus {
        try await request("wallet")
    }

    public func receive(amount: Double, note: String) async throws -> WalletStatus {
        let body = try encodeBody(ReceiveRequest(amount_usd: amount, note: note))
        return try await request("wallet/receive", method: "POST", body: body)
    }

    public func send(amount: Double, dest: String, note: String) async throws -> WalletStatus {
        let body = try encodeBody(SendRequest(amount_usd: amount, dest: dest, note: note))
        return try await request("wallet/send", method: "POST", body: body)
    }

    public func withdraw(amount: Double, source: String) async throws -> WalletStatus {
        let body = try encodeBody(WithdrawRequest(amount_usd: amount, source: source))
        return try await request("wallet/withdraw", method: "POST", body: body)
    }

    // MARK: - Trade

    public func fetchTradeStatus() async throws -> TradeStatus {
        try await request("trade/status")
    }

    public func fetchMarkets(limit: Int = 30) async throws -> [MarketItem] {
        let response: MarketsResponse = try await request("trade/markets", query: ["limit": String(limit)])
        return response.markets
    }

    public func quote(query: String) async throws -> MarketItem {
        try await request("trade/quote", query: ["q": query])
    }

    public func buy(
        mint: String,
        amountUsd: Double,
        stopLossPct: Double? = nil,
        takeProfitPct: Double? = nil
    ) async throws -> TradeStatus {
        let body = try encodeBody(
            BuyRequest(
                mint: mint,
                amount_usd: amountUsd,
                stop_loss_pct: stopLossPct,
                take_profit_pct: takeProfitPct
            )
        )
        return try await request("trade/buy", method: "POST", body: body)
    }

    public func sell(mint: String, amountUsd: Double? = nil) async throws -> TradeStatus {
        let body = try encodeBody(SellRequest(mint: mint, amount_usd: amountUsd))
        return try await request("trade/sell", method: "POST", body: body)
    }

    public func markTrades() async throws -> TradeStatus {
        try await request("trade/mark", method: "POST")
    }

    // MARK: - Copy

    public func fetchCopyStatus() async throws -> CopyStatus {
        try await request("copy/status")
    }

    public func fetchFollowedWallets() async throws -> [String: FollowedWallet] {
        let response: WalletsResponse = try await request("copy/wallets")
        return response.wallets
    }

    public func followWallet(address: String, label: String) async throws -> [String: Any] {
        let body = try encodeBody(FollowRequest(address: address, label: label))
        return try await requestObject("copy/wallets", method: "POST", body: body)
    }

    public func unfollowWallet(address: String) async throws -> [String: Any] {
        try await requestObject("copy/wallets/\(address)", method: "DELETE")
    }

    public func triggerCopyScan() async throws -> [String: Any] {
        try await requestObject("copy/scan", method: "POST")
    }

    public func closeCopyPosition(mint: String) async throws -> [String: Any] {
        struct CloseBody: Encodable { let mint: String }
        return try await requestObject("copy/close", method: "POST", body: try encodeBody(CloseBody(mint: mint)))
    }

    // MARK: - Finder

    private struct FiltersResponse: Decodable { let filters: [String: Double] }

    private func decodeFilters(_ data: Data) throws -> [String: Double] {
        if let wrapper = try? decoder.decode(FiltersResponse.self, from: data) {
            return wrapper.filters
        }
        do {
            return try decoder.decode([String: Double].self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }

    public func fetchFinderFilters() async throws -> [String: Double] {
        try decodeFilters(try await send(path: "finder/filters"))
    }

    public func scanFinder() async throws -> [String: Any] {
        try await requestObject("finder/scan", method: "POST")
    }

    public func updateFinderFilter(key: String, value: Double) async throws -> [String: Double] {
        struct FilterBody: Encodable {
            let key: String
            let value: Double
        }
        let body = try encodeBody(FilterBody(key: key, value: value))
        return try decodeFilters(try await send(path: "finder/filters", method: "POST", body: body))
    }

    public func applyFinderPreset(_ name: String) async throws -> [String: Double] {
        struct PresetBody: Encodable { let name: String }
        let body = try encodeBody(PresetBody(name: name))
        return try decodeFilters(try await send(path: "finder/preset", method: "POST", body: body))
    }

    // MARK: - Ops (killswitch)

    public func freeze(desk: String, reason: String) async throws -> [String: Any] {
        struct FreezeBody: Encodable {
            let desk: String
            let reason: String
        }
        let body = try encodeBody(FreezeBody(desk: desk, reason: reason))
        return try await requestObject("ops/freeze", method: "POST", body: body)
    }

    public func thaw(desk: String) async throws -> [String: Any] {
        struct ThawBody: Encodable { let desk: String }
        let body = try encodeBody(ThawBody(desk: desk))
        return try await requestObject("ops/thaw", method: "POST", body: body)
    }
}
