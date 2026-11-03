import NexusCore
import SwiftUI

/// Yield: keep USDC in whichever allowlisted lending pool pays the most.
public struct YieldDeskView: View {
    @ObservedObject var state: AppState

    public var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {

                HStack(alignment: .top) {
                    DeskHeader(
                        "Yield",
                        title: "Earn interest on USDC.",
                        subtitle: "The rules pick the highest-paying approved pool and move your cash there."
                    )
                    Spacer(minLength: 12)
                    Button {
                        Task { await state.runYieldTick() }
                    } label: {
                        Label("Run tick", systemImage: "arrow.triangle.2.circlepath")
                    }
                    .buttonStyle(ScoutGhostButtonStyle())
                }

                // Where the money is right now, and what it earns.
                StatRow([
                    StatTile(
                        "Earning now",
                        value: Formatters.usd(state.yieldStatus?.position?.amount_usd),
                        caption: state.yieldStatus?.position?.project ?? "nothing deployed",
                        valueColor: Theme.green
                    ),
                    StatTile(
                        "Interest rate",
                        value: Formatters.pct(state.yieldStatus?.position?.apy),
                        caption: "annual"
                    ),
                    StatTile(
                        "Earns per day",
                        value: Formatters.usd(state.yieldStatus?.paper_per_day),
                        caption: "simulated"
                    ),
                    StatTile(
                        "Idle cash",
                        value: Formatters.usd(state.yieldStatus?.cash_usd),
                        caption: "not earning anything"
                    )
                ])

                // The pools it is allowed to choose between.
                Panel("Lending pools", subtitle: "Only USDC pools on the approved list are ever considered.") {
                    RowList(
                        count: state.yieldStands.count,
                        empty: {
                            EmptyState(
                                icon: "percent",
                                title: "No pools loaded",
                                message: "Start the server, then press Update all to scan."
                            )
                        }
                    ) {
                        ForEach(state.yieldStands) { pool in
                            TableRow {
                                HStack(spacing: 8) {
                                    Text(pool.project ?? "Pool")
                                        .font(.system(size: 13, weight: .medium))
                                        .foregroundColor(Theme.ink)
                                    if pool.project == currentProject {
                                        Tag("In use", color: Theme.green)
                                    }
                                }
                            } trailing: {
                                HStack(spacing: 14) {
                                    Text(Formatters.pct(pool.apy))
                                        .font(Theme.bodyNumber)
                                        .foregroundColor(Theme.green)
                                    Text(Formatters.usd(pool.tvl_usd))
                                        .font(Theme.captionNumber)
                                        .foregroundColor(Theme.muted)
                                        .frame(width: 92, alignment: .trailing)
                                }
                            }
                        }
                    }
                }

                // What would happen if the rules allowed a move.
                if let plan = state.yieldPlan {
                    Panel("Next decision", subtitle: "The rules decide this, not you.") {
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Text(plan.would_send == true ? "Would move to" : "Staying put")
                                    .font(Theme.body)
                                    .foregroundColor(Theme.ink)
                                if let dest = plan.dest, let project = dest.project {
                                    Tag(project, color: Theme.violetLt)
                                }
                                Spacer()
                            }

                            if let blockers = plan.blockers, !blockers.isEmpty {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text("Why it cannot move yet")
                                        .font(Theme.label)
                                        .textCase(.uppercase)
                                        .tracking(0.6)
                                        .foregroundColor(Theme.dim)
                                    ForEach(blockers, id: \.self) { blocker in
                                        Text(blocker)
                                            .font(Theme.body)
                                            .foregroundColor(Theme.loss)
                                    }
                                }
                            } else {
                                Text("No blockers.")
                                    .font(Theme.caption)
                                    .foregroundColor(Theme.muted)
                            }
                        }
                    }
                }
            }
            .padding(Theme.pagePadding)
        }
    }

    private var currentProject: String? {
        state.yieldStatus?.position?.project
    }
}
