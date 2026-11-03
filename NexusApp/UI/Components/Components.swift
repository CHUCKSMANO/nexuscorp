import NexusCore
import SwiftUI

// MARK: - Stat tile

/// One number with a label above it and context below.
///
/// This is the app's main unit of information. The label is a small uppercase
/// eyebrow, the value is the loudest thing in the tile, and the caption explains
/// it in words.
public struct StatTile: View {
    private let label: String
    private let value: String
    private let caption: String?
    private let valueColor: Color
    private let gradientValue: Bool

    public init(
        _ label: String,
        value: String,
        caption: String? = nil,
        valueColor: Color = Theme.money,
        gradientValue: Bool = false
    ) {
        self.label = label
        self.value = value
        self.caption = caption
        self.valueColor = valueColor
        self.gradientValue = gradientValue
    }

    public var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(label.uppercased())
                .font(Theme.label)
                .tracking(0.7)
                .foregroundColor(Theme.dim)
                .lineLimit(1)

            Text(value)
                .font(Theme.metricNumber)
                .foregroundColor(gradientValue ? nil : valueColor)
                .foregroundStyle(gradientValue ? AnyShapeStyle(Theme.statGradient) : AnyShapeStyle(valueColor))
                .lineLimit(1)
                .minimumScaleFactor(0.6)

            if let caption {
                Text(caption)
                    .font(Theme.caption)
                    .foregroundColor(Theme.muted)
                    .lineLimit(1)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .card()
    }
}

/// A row of stat tiles that wraps onto more lines as the window narrows.
public struct StatRow: View {
    private let tiles: [StatTile]

    public init(_ tiles: [StatTile]) {
        self.tiles = tiles
    }

    public var body: some View {
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .top, spacing: Theme.gap) { ForEach(Array(tiles.enumerated()), id: \.offset) { $1 } }
            VStack(spacing: Theme.gap) { ForEach(Array(tiles.enumerated()), id: \.offset) { $1 } }
        }
    }
}

// MARK: - Stat band

/// The rounded, softly gradient-band that groups headline statistics.
public struct StatBand<Content: View>: View {
    private let content: Content

    public init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }

    public var body: some View {
        content
            .padding(24)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .fill(
                        LinearGradient(
                            colors: [Theme.violet.opacity(0.10), Theme.blue.opacity(0.06)],
                            startPoint: .topLeading, endPoint: .bottomTrailing
                        )
                    )
            )
            .overlay(
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .stroke(Theme.line, lineWidth: 1)
            )
    }
}

/// A statistic stacked inside a StatBand.
public struct HeroStat: View {
    private let label: String
    private let value: String
    private let caption: String?

    public init(_ label: String, value: String, caption: String? = nil) {
        self.label = label
        self.value = value
        self.caption = caption
    }

    public var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label.uppercased())
                .font(Theme.label)
                .tracking(0.7)
                .foregroundColor(Theme.muted)
            Text(value)
                .font(.system(size: 30, weight: .bold, design: .default).monospacedDigit())
                .foregroundStyle(Theme.statGradient)
                .lineLimit(1)
                .minimumScaleFactor(0.6)
            if let caption {
                Text(caption)
                    .font(Theme.caption)
                    .foregroundColor(Theme.muted)
                    .lineLimit(1)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Panel

/// A titled panel. The standard container for a desk section.
public struct Panel<Content: View>: View {
    private let title: String
    private let subtitle: String?
    private let content: Content

    public init(_ title: String, subtitle: String? = nil, @ViewBuilder content: () -> Content) {
        self.title = title
        self.subtitle = subtitle
        self.content = content()
    }

    public var body: some View {
        VStack(alignment: .leading, spacing: Theme.gap) {
            VStack(alignment: .leading, spacing: 3) {
                Text(title)
                    .font(Theme.heading)
                    .foregroundColor(Theme.ink)
                if let subtitle {
                    Text(subtitle)
                        .font(Theme.caption)
                        .foregroundColor(Theme.muted)
                }
            }
            content
        }
        .card()
    }
}

// MARK: - Empty state

/// What a panel shows when it has nothing to show. Always says what to do next.
public struct EmptyState: View {
    private let icon: String
    private let title: String
    private let message: String?

    public init(icon: String, title: String, message: String? = nil) {
        self.icon = icon
        self.title = title
        self.message = message
    }

    public var body: some View {
        VStack(spacing: 8) {
            Image(systemName: icon)
                .font(.system(size: 18))
                .foregroundColor(Theme.violetLt)
                .frame(width: 40, height: 40)
                .background(
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .fill(Theme.violet.opacity(0.12))
                )
            Text(title)
                .font(.system(size: 13, weight: .medium))
                .foregroundColor(Theme.ink)
            if let message {
                Text(message)
                    .font(Theme.caption)
                    .foregroundColor(Theme.muted)
                    .multilineTextAlignment(.center)
            }
        }
        .frame(maxWidth: .infinity, minHeight: 96)
    }
}

// MARK: - State badge

/// On/off state, stated in words. `frozen` is a safety control, so it gets red.
public struct StateBadge: View {
    public enum Kind {
        case running, stopped, frozen, ready

        var text: String {
            switch self {
            case .running: return "Running"
            case .stopped: return "Stopped"
            case .frozen: return "Frozen"
            case .ready: return "Ready"
            }
        }

        var color: Color {
            switch self {
            case .running, .ready: return Theme.green
            case .stopped: return Theme.muted
            case .frozen: return Theme.red
            }
        }

        var icon: String {
            switch self {
            case .running: return "play.circle.fill"
            case .stopped: return "stop.circle"
            case .frozen: return "pause.circle.fill"
            case .ready: return "circle.dashed"
            }
        }
    }

    private let kind: Kind

    public init(_ kind: Kind) {
        self.kind = kind
    }

    public var body: some View {
        HStack(spacing: 5) {
            Circle()
                .fill(kind.color)
                .frame(width: 6, height: 6)
            Text(kind.text)
                .font(.system(size: 11, weight: .semibold))
        }
        .foregroundColor(kind.color)
        .padding(.horizontal, 10)
        .padding(.vertical, 5)
        .background(
            Capsule(style: .continuous)
                .fill(kind.color.opacity(0.12))
        )
    }
}

// MARK: - Tag

/// A small labeled chip, used to categorise a card.
public struct Tag: View {
    private let text: String
    private let color: Color

    public init(_ text: String, color: Color = Theme.violetLt) {
        self.text = text
        self.color = color
    }

    public var body: some View {
        Text(text.uppercased())
            .font(.system(size: 10, weight: .heavy))
            .tracking(0.5)
            .foregroundColor(color)
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(
                RoundedRectangle(cornerRadius: 6, style: .continuous)
                    .fill(color.opacity(0.14))
            )
    }
}

// MARK: - Desk card

/// A card that summarises one desk: an icon, its name, the one fact that
/// matters, and its run state.
public struct DeskCard: View {
    private let title: String
    private let icon: String
    private let detail: String
    private let accent: Color
    private let frozen: Bool

    public init(title: String, icon: String, detail: String, accent: Color, frozen: Bool) {
        self.title = title
        self.icon = icon
        self.detail = detail
        self.accent = accent
        self.frozen = frozen
    }

    public var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
                Image(systemName: icon)
                    .font(.system(size: 15))
                    .foregroundColor(accent)
                    .frame(width: 34, height: 34)
                    .background(
                        RoundedRectangle(cornerRadius: 10, style: .continuous)
                            .fill(accent.opacity(0.14))
                    )
                Text(title)
                    .font(Theme.heading)
                    .foregroundColor(Theme.ink)
                Spacer(minLength: 4)
                StateBadge(frozen ? .frozen : .ready)
            }
            Text(detail)
                .font(Theme.bodyNumber)
                .foregroundColor(Theme.muted)
                .lineLimit(2)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .card()
    }
}

// MARK: - Desk header

/// The heading at the top of every desk: an eyebrow, a title, and one line of
/// plain-language context.
public struct DeskHeader: View {
    private let kicker: String
    private let title: String
    private let subtitle: String?

    public init(_ kicker: String, title: String, subtitle: String? = nil) {
        self.kicker = kicker
        self.title = title
        self.subtitle = subtitle
    }

    public var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Kicker(kicker)
            Text(title)
                .font(.system(size: 24, weight: .bold))
                .tracking(-0.3)
                .foregroundColor(Theme.ink)
            if let subtitle {
                Text(subtitle)
                    .font(Theme.body)
                    .foregroundColor(Theme.muted)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Inputs

/// A dark, bordered input that matches the card language.
public struct ScoutFieldModifier: ViewModifier {
    public func body(content: Content) -> some View {
        content
            .textFieldStyle(.plain)
            .font(.system(size: 13))
            .foregroundColor(Theme.ink)
            .padding(.horizontal, 12)
            .padding(.vertical, 9)
            .background(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .fill(Theme.raised)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .stroke(Theme.line, lineWidth: 1)
            )
    }
}

public extension View {
    func scoutField() -> some View {
        modifier(ScoutFieldModifier())
    }
}

// MARK: - Rows

/// A scrollable list of rows, or an explanation when there are none.
public struct RowList<Content: View>: View {
    private let rows: Int
    private let empty: EmptyState
    private let content: Content

    public init(
        count: Int,
        @ViewBuilder empty: () -> EmptyState,
        @ViewBuilder content: () -> Content
    ) {
        self.rows = count
        self.empty = empty()
        self.content = content()
    }

    public var body: some View {
        if rows == 0 {
            empty
        } else {
            ScrollView {
                VStack(spacing: 0) {
                    content
                }
            }
        }
    }
}

/// A single row inside a RowList, with a hairline underneath.
public struct TableRow<Leading: View, Trailing: View>: View {
    private let leading: Leading
    private let trailing: Trailing

    public init(@ViewBuilder leading: () -> Leading, @ViewBuilder trailing: () -> Trailing) {
        self.leading = leading()
        self.trailing = trailing()
    }

    public var body: some View {
        HStack(spacing: 10) {
            leading
            Spacer(minLength: 8)
            trailing
        }
        .padding(.vertical, 9)
        .overlay(alignment: .bottom) {
            Rectangle()
                .fill(Theme.line)
                .frame(height: 1)
        }
    }
}

// MARK: - Shared lists

public extension View {
    /// A list of completed trades, newest first. Shared by the Trade and Copy
    /// desks, which show the same fill history for different sources.
    func fillsList(_ fills: [Fill], emptyTitle: String) -> some View {
        RowList(
            count: fills.count,
            empty: {
                EmptyState(icon: "clock", title: emptyTitle)
            }
        ) {
            ForEach(fills.prefix(10)) { fill in
                TableRow {
                    HStack(spacing: 6) {
                        Text(fill.side == "sell" ? "Sold" : "Bought")
                            .font(Theme.caption)
                            .foregroundColor(fill.side == "sell" ? Theme.loss : Theme.profit)
                        Text(fill.symbol ?? Formatters.shortAddress(fill.mint))
                            .font(.system(size: 13, weight: .medium))
                            .foregroundColor(Theme.ink)
                    }
                } trailing: {
                    Text(Formatters.usd(fill.effectiveUsd))
                        .font(Theme.bodyNumber)
                        .foregroundColor(Theme.ink)
                }
            }
        }
    }
}
