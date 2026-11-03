import NexusCore
import SwiftUI

/// Wallet: the hub that holds cash and moves it between desks.
public struct WalletDeskView: View {
    @ObservedObject var state: AppState

    @State private var depositAmount: String = "500.00"
    @State private var depositNote: String = ""
    @State private var sendAmount: String = "100.00"
    @State private var sendDestination: String = "yield"
    @State private var sendAddress: String = ""
    @State private var copied: Bool = false

    public var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {

                DeskHeader(
                    "Wallet",
                    title: "Hold and move money.",
                    subtitle: "The hub wallet keeps cash, and shifts it to whichever desk needs it."
                )

                StatRow([
                    StatTile("Total value", value: Formatters.usd(state.wallet?.nav_usd), gradientValue: true),
                    StatTile("Ready to spend", value: Formatters.usd(state.wallet?.cash_usd)),
                    StatTile("Already working", value: Formatters.usd(state.wallet?.deployed_usd)),
                    StatTile(
                        "SOL for fees",
                        value: String(format: "%.4f", sol),
                        caption: sol < 0.02 ? "too little for a transaction" : "enough for fees"
                    )
                ])

                receiveAddress

                HStack(alignment: .top, spacing: Theme.gap) {
                    moveMoney
                    history
                }
            }
            .padding(Theme.pagePadding)
        }
    }

    private var sol: Double {
        state.wallet?.chain?.mainnet_sol ?? state.wallet?.chain?.devnet_sol ?? 0.0
    }

    // MARK: - Receive

    private var receiveAddress: some View {
        Panel("Receive", subtitle: "Send funds to this address to add money.") {
            HStack(spacing: 8) {
                Text(state.wallet?.receive_address ?? "Not connected")
                    .font(Theme.code)
                    .foregroundColor(Theme.ink)
                    .textSelection(.enabled)
                    .lineLimit(1)
                    .truncationMode(.middle)
                Spacer(minLength: 8)
                Button {
                    guard let address = state.wallet?.receive_address else { return }
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(address, forType: .string)
                    copied = true
                    DispatchQueue.main.asyncAfter(deadline: .now() + 2) { copied = false }
                } label: {
                    Label(copied ? "Copied" : "Copy", systemImage: copied ? "checkmark" : "doc.on.doc")
                        .labelStyle(.titleAndIcon)
                }
                .buttonStyle(ScoutGhostButtonStyle())
                .disabled(state.wallet?.receive_address == nil)
            }
        }
    }

    // MARK: - Move money

    private var moveMoney: some View {
        Panel("Move money", subtitle: "Add funds, or shift them to another desk.") {
            VStack(alignment: .leading, spacing: Theme.gap) {

                VStack(alignment: .leading, spacing: 6) {
                    Text("Add funds")
                        .font(Theme.label)
                        .textCase(.uppercase)
                        .tracking(0.6)
                        .foregroundColor(Theme.dim)
                    HStack(spacing: 8) {
                        TextField("Amount", text: $depositAmount)
                            .scoutField()
                        TextField("Note (optional)", text: $depositNote)
                            .scoutField()
                        Button("Add") {
                            Task { await state.depositHub(amount: Double(depositAmount) ?? 0, note: depositNote) }
                        }
                        .buttonStyle(ScoutPrimaryButtonStyle())
                    }
                }

                Divider().overlay(Theme.line)

                VStack(alignment: .leading, spacing: 6) {
                    Text("Send to a desk")
                        .font(Theme.label)
                        .textCase(.uppercase)
                        .tracking(0.6)
                        .foregroundColor(Theme.dim)
                    Picker("", selection: $sendDestination) {
                        Text("Yield").tag("yield")
                        Text("Trade").tag("trade")
                        Text("Copy").tag("copy")
                    }
                    .labelsHidden()
                    .pickerStyle(.segmented)
                    .tint(Theme.violet)

                    HStack(spacing: 8) {
                        TextField("Amount", text: $sendAmount)
                            .scoutField()
                        Button("Send") {
                            Task { await state.sendHub(amount: Double(sendAmount) ?? 0, dest: sendDestination, note: "") }
                        }
                        .buttonStyle(ScoutGhostButtonStyle())
                    }

                    HStack(spacing: 8) {
                        TextField("Or a wallet address", text: $sendAddress)
                            .scoutField()
                        Button("Send there") {
                            Task { await state.sendHub(amount: Double(sendAmount) ?? 0, dest: sendAddress, note: "") }
                        }
                        .buttonStyle(ScoutGhostButtonStyle())
                        .disabled(sendAddress.trimmingCharacters(in: .whitespaces).isEmpty)
                    }
                }
            }
        }
    }

    // MARK: - History

    private var history: some View {
        Panel("Money movements") {
            RowList(
                count: state.wallet?.ledger?.count ?? 0,
                empty: {
                    EmptyState(icon: "list.bullet", title: "No movements yet")
                }
            ) {
                ForEach(state.wallet?.ledger?.prefix(12) ?? []) { entry in
                    TableRow {
                        VStack(alignment: .leading, spacing: 1) {
                            Text(entry.note ?? entry.kind ?? "Movement")
                                .font(.system(size: 13))
                                .foregroundColor(Theme.ink)
                            Text("\(entry.from ?? "—") → \(entry.to ?? "—")")
                                .font(Theme.caption)
                                .foregroundColor(Theme.dim)
                        }
                    } trailing: {
                        Text(Formatters.usd(entry.amount_usd))
                            .font(Theme.bodyNumber)
                            .foregroundColor(Theme.ink)
                    }
                }
            }
        }
    }
}
