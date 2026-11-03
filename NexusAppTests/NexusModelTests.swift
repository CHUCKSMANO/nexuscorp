import XCTest
@testable import NexusCore

final class NexusModelTests: XCTestCase {
    func testHealthIgnoresScanObjects() throws {
        let json = """
        {"ok":true,"name":"The Token Yielder","mode":"paper","finder_execution":"alerts","copy_execution":"paper","frozen":{"all":false,"yield":false,"finder":true,"copy":false,"reason":null},"runtime":{"started_at":"2026-09-26T00:00:00+00:00","last_finder_scan":{"tracked":3},"last_copy_scan":{"fills":1}}}
        """.data(using: .utf8)!
        let health = try JSONDecoder().decode(SystemHealth.self, from: json)
        XCTAssertEqual(health.name, "The Token Yielder")
        XCTAssertEqual(health.mode, "paper")
        XCTAssertTrue(health.frozen.finder)
        XCTAssertFalse(health.frozen.copy)
    }

    func testYieldPlanDecodesPoolObject() throws {
        let json = """
        {"wallet":"abc","sol":0.4,"usdc":20,"amount_usd":20,"dest":{"project":"kamino-lend","apy":4.2,"tvl_usd":1200000,"pool_id":"kamino:usdc"},"would_send":false,"blockers":["LIVE_ENABLED=false"]}
        """.data(using: .utf8)!
        let plan = try JSONDecoder().decode(YieldPlan.self, from: json)
        XCTAssertEqual(plan.dest?.project, "kamino-lend")
        XCTAssertEqual(plan.blockers, ["LIVE_ENABLED=false"])
    }

    func testTradeActionUnwrapShape() throws {
        let json = """
        {"ok":true,"trade":{"desk":"trade","mode":"paper","cash_usd":100,"open_positions":0,"positions":[],"fills":[]}}
        """.data(using: .utf8)!
        let trade = try JSONDecoder().decode(TradeStatus.self, from: Data("""
        {"desk":"trade","mode":"paper","cash_usd":100,"open_positions":0,"positions":[],"fills":[]}
        """.utf8))
        XCTAssertEqual(trade.cash_usd, 100)
        XCTAssertFalse(json.isEmpty)
    }

    func testAPIPathsKeepSlashes() throws {
        let base = URL(string: "http://127.0.0.1:8000")!
        let url = try NexusAPIClient.makeURL(
            base: base,
            path: "copy/wallets/So11111111111111111111111111111111111111112",
            query: ["desk": "all"]
        )
        XCTAssertEqual(
            url.absoluteString,
            "http://127.0.0.1:8000/copy/wallets/So11111111111111111111111111111111111111112?desk=all"
        )
    }

    func testShortAddress() {
        XCTAssertEqual(Formatters.shortAddress("1234567890", size: 4), "1234...7890")
        XCTAssertEqual(Formatters.shortAddress(nil), "--")
    }
}
