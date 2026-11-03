import NexusCore
import SwiftUI
import WebKit

/// Renders a token's chart URL in an embedded web view. When a token has no
/// chart link yet, it says so rather than showing a blank rectangle.
public struct TokenChartView: View {
    private let urlString: String?

    public init(urlString: String?) {
        self.urlString = urlString
    }

    public var body: some View {
        Group {
            if let urlString, let url = URL(string: urlString), !urlString.isEmpty {
                ChartWebView(url: url)
            } else {
                EmptyState(
                    icon: "chart.line.uptrend.xyaxis",
                    title: "No chart yet",
                    message: "This token has no chart link."
                )
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .background(Theme.card)
    }
}

private struct ChartWebView: NSViewRepresentable {
    let url: URL

    func makeNSView(context: Context) -> WKWebView {
        let view = WKWebView()
        view.underPageBackgroundColor = .clear
        return view
    }

    func updateNSView(_ nsView: WKWebView, context: Context) {
        if nsView.url != url {
            nsView.load(URLRequest(url: url))
        }
    }
}
