import SwiftUI

/// Shared visual language for the whole app.
///
/// The look follows Scout Finance's dark trading UI: near-black surfaces, a
/// single violet accent for action, green/red reserved for money direction, and
/// generous corner radii. Colour is still meaning-first — green is profit, red
/// is risk, violet is "this is a control".
public enum Theme {

    // MARK: - Palette

    /// App background, behind every surface.
    public static let bg = Color(hex: 0x08090C)
    /// The top navigation strip, a hair lighter than the background.
    public static let nav = Color(hex: 0x0A0B0F)
    /// Cards and panels.
    public static let card = Color(hex: 0x0E1015)
    /// Slightly raised fill (inputs, chips).
    public static let raised = Color.white.opacity(0.05)

    /// Primary text.
    public static let ink = Color(hex: 0xF7F8FA)
    /// Secondary text.
    public static let muted = Color(hex: 0x9CA3AF)
    /// Tertiary text and metadata.
    public static let dim = Color(hex: 0x6B7280)

    /// Accent, used for action and selected state.
    public static let violet = Color(hex: 0x8B5CF6)
    public static let violetLt = Color(hex: 0xA78BFA)
    public static let blue = Color(hex: 0x3B82F6)
    /// Money up.
    public static let green = Color(hex: 0x34D399)
    /// A warning/paused accent.
    public static let gold = Color(hex: 0xE7B94E)
    /// Money down / risk.
    public static let red = Color(hex: 0xF87171)

    /// The one hairline used for every border and divider.
    public static let line = Color.white.opacity(0.08)
    public static let lineStrong = Color.white.opacity(0.16)

    // MARK: - Text

    /// The largest number on screen.
    public static let display = Font.system(size: 30, weight: .bold)
    /// Panel titles.
    public static let heading = Font.system(size: 15, weight: .bold)
    /// Hero figures.
    public static let metric = Font.system(size: 24, weight: .bold)
    /// Body content, table cells.
    public static let body = Font.system(size: 13)
    /// Labels above values, section headings.
    public static let label = Font.system(size: 11, weight: .semibold)
    /// Supporting text under a value.
    public static let caption = Font.system(size: 11)
    /// Numeric variants, tabular so columns line up.
    public static let metricNumber = Font.system(size: 24, weight: .bold).monospacedDigit()
    public static let bodyNumber = Font.system(size: 13).monospacedDigit()
    public static let captionNumber = Font.system(size: 11).monospacedDigit()
    /// Addresses, logs, anything where character identity matters.
    public static let code = Font.system(size: 11, design: .monospaced)

    // MARK: - Meaning

    public static let money = ink
    public static let profit = green
    public static let loss = red
    public static let hairline = line

    /// Green when up, red when down. Used for every P&L figure.
    public static func pnl(_ value: Double) -> Color {
        if value > 0.0001 { return profit }
        if value < -0.0001 { return loss }
        return muted
    }

    /// Green when a desk is live, red when frozen, grey when it has no data.
    public static func status(_ isOn: Bool, hasData: Bool = true) -> Color {
        guard hasData else { return muted }
        return isOn ? profit : loss
    }

    // MARK: - Gradients

    /// Scout's headline gradient: white into lavender into sky.
    public static let heroGradient = LinearGradient(
        colors: [Color(hex: 0xFFFFFF), Color(hex: 0xC4B5FD), Color(hex: 0x7DD3FC)],
        startPoint: .leading, endPoint: .trailing
    )

    /// White into violet, for statistic figures on the stats band.
    public static let statGradient = LinearGradient(
        colors: [Color(hex: 0xFFFFFF), violetLt],
        startPoint: .topLeading, endPoint: .bottomTrailing
    )

    /// Violet into blue, the action gradient.
    public static let accentGradient = LinearGradient(
        colors: [violet, blue],
        startPoint: .topLeading, endPoint: .bottomTrailing
    )

    // MARK: - Metrics

    public static let cardRadius: CGFloat = 16
    public static let cardPadding: CGFloat = 18
    public static let gap: CGFloat = 12
    public static let pagePadding: CGFloat = 22
}

// MARK: - Hex

public extension Color {
    /// `Color(hex: 0x8B5CF6)` — sRGB from a 24-bit hex literal.
    init(hex: UInt32, alpha: Double = 1.0) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xFF) / 255.0,
            green: Double((hex >> 8) & 0xFF) / 255.0,
            blue: Double(hex & 0xFF) / 255.0,
            opacity: alpha
        )
    }
}

// MARK: - Surfaces

/// A surface: the one card style used by every panel in the app.
public struct CardBackground: ViewModifier {
    public var padding: CGFloat = Theme.cardPadding

    public init(padding: CGFloat = Theme.cardPadding) {
        self.padding = padding
    }

    public func body(content: Content) -> some View {
        content
            .padding(padding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: Theme.cardRadius, style: .continuous)
                    .fill(Theme.card)
            )
            .overlay(
                RoundedRectangle(cornerRadius: Theme.cardRadius, style: .continuous)
                    .stroke(Theme.line, lineWidth: 1)
            )
    }
}

public extension View {
    func card(padding: CGFloat = Theme.cardPadding) -> some View {
        modifier(CardBackground(padding: padding))
    }
}

// MARK: - Kicker

/// The small uppercase eyebrow that sits above a heading, in violet.
public struct Kicker: View {
    private let text: String

    public init(_ text: String) {
        self.text = text
    }

    public var body: some View {
        Text(text.uppercased())
            .font(Theme.label)
            .tracking(0.9)
            .foregroundColor(Theme.violetLt)
    }
}

// MARK: - Section header

/// A section heading, with an optional trailing control.
public struct SectionHeader<Accessory: View>: View {
    private let title: String
    private let accessory: Accessory

    public init(_ title: String, @ViewBuilder accessory: () -> Accessory) {
        self.title = title
        self.accessory = accessory()
    }

    public var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(title)
                .font(Theme.label)
                .textCase(.uppercase)
                .tracking(0.6)
                .foregroundColor(Theme.muted)
            Spacer(minLength: 8)
            accessory
        }
    }
}

public extension SectionHeader where Accessory == EmptyView {
    init(_ title: String) {
        self.init(title) { EmptyView() }
    }
}

// MARK: - Buttons

/// The violet action button.
public struct ScoutPrimaryButtonStyle: ButtonStyle {
    public init() {}

    public func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 13, weight: .semibold))
            .foregroundColor(.white)
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .background(
                RoundedRectangle(cornerRadius: 11, style: .continuous)
                    .fill(Theme.violet.opacity(configuration.isPressed ? 0.82 : 1.0))
            )
            .contentShape(RoundedRectangle(cornerRadius: 11, style: .continuous))
    }
}

/// A quiet button: translucent fill with a hairline border.
public struct ScoutGhostButtonStyle: ButtonStyle {
    public init() {}

    public func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 13, weight: .semibold))
            .foregroundColor(Theme.ink)
            .padding(.horizontal, 14)
            .padding(.vertical, 8)
            .background(
                RoundedRectangle(cornerRadius: 11, style: .continuous)
                    .fill(Color.white.opacity(configuration.isPressed ? 0.12 : 0.06))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 11, style: .continuous)
                    .stroke(Theme.line, lineWidth: 1)
            )
            .contentShape(RoundedRectangle(cornerRadius: 11, style: .continuous))
    }
}

/// A destructive button, for stopping things.
public struct ScoutDangerButtonStyle: ButtonStyle {
    public init() {}

    public func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 13, weight: .semibold))
            .foregroundColor(.white)
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .background(
                RoundedRectangle(cornerRadius: 11, style: .continuous)
                    .fill(Theme.red.opacity(configuration.isPressed ? 0.82 : 1.0))
            )
            .contentShape(RoundedRectangle(cornerRadius: 11, style: .continuous))
    }
}
