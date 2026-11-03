(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const REFRESH_MS = 20000;
  let timer = null;

  const esc = (value) =>
    String(value == null ? "—" : value).replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[ch]));

  const usd = (value, digits = 2) => {
    const n = Number(value);
    if (!Number.isFinite(n)) return "—";
    return n.toLocaleString("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
  };

  const compactUsd = (value) => {
    const n = Number(value);
    if (!Number.isFinite(n)) return "—";
    if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
    if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
    if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(1)}K`;
    return usd(n, 0);
  };

  const apy = (value) => {
    const n = Number(value);
    return Number.isFinite(n) ? `${n.toFixed(2)}%` : "—";
  };

  const pct = (value) => {
    const n = Number(value);
    if (!Number.isFinite(n)) return "—";
    return `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
  };

  const dirClass = (value) => {
    const n = Number(value);
    if (!Number.isFinite(n) || Math.abs(n) < 0.005) return "flat";
    return n > 0 ? "up" : "down";
  };

  const short = (value, head = 4, tail = 4) => {
    const s = String(value || "");
    return s.length > head + tail + 3 ? `${s.slice(0, head)}…${s.slice(-tail)}` : s || "—";
  };

  const time = (iso) => {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  const relTime = (iso) => {
    if (!iso) return "never";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso);
    const secs = Math.max(0, Math.round((Date.now() - d.getTime()) / 1000));
    if (secs < 60) return `${secs}s ago`;
    if (secs < 3600) return `${Math.round(secs / 60)}m ago`;
    if (secs < 86400) return `${Math.round(secs / 3600)}h ago`;
    return `${Math.round(secs / 86400)}d ago`;
  };

  async function get(path) {
    const res = await fetch(path, { headers: { Accept: "application/json" }, cache: "no-store" });
    let data = null;
    try {
      data = await res.json();
    } catch (_) {
      data = null;
    }
    if (!res.ok) {
      throw new Error((data && data.detail) || `request failed (${res.status})`);
    }
    return data;
  }

  async function post(path, body) {
    const res = await fetch(path, {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    let data = null;
    try {
      data = await res.json();
    } catch (_) {
      data = null;
    }
    if (!res.ok) {
      throw new Error((data && data.detail) || `request failed (${res.status})`);
    }
    return data;
  }

  let toastTimer = null;
  function toast(message, isError = false) {
    const node = $("toast");
    node.textContent = message;
    node.classList.toggle("err", Boolean(isError));
    node.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => node.classList.remove("show"), 3600);
  }

  function setTag(id, text, kind) {
    const node = $(id);
    if (!node) return;
    node.textContent = text;
    node.className = `tag${kind ? ` ${kind}` : ""}`;
  }

  function rows(items, render, emptyText) {
    if (!items || !items.length) return `<div class="empty">${esc(emptyText)}</div>`;
    return `<div class="rows">${items.map(render).join("")}</div>`;
  }

  function renderHero(status) {
    const wallet = status.wallet || {};
    const y = status.yield || {};
    const trade = status.trade || {};
    const copy = status.copy || {};
    const openPositions =
      Number(trade.open_positions || 0) + Number(copy.open_positions || 0);

    $("stat-nav").textContent = usd(wallet.nav_usd);
    $("stat-nav-sub").textContent = `${wallet.mode || "paper"} book`;
    $("stat-idle").textContent = usd(wallet.idle_usd);
    $("stat-deployed").textContent = usd(wallet.deployed_usd);
    $("stat-perday").textContent = usd(y.paper_per_day, 4);
    $("stat-lifetime").textContent = usd(y.lifetime_earned_usd, 4);
    $("stat-positions").textContent = String(openPositions);

    const frozen = status.frozen || {};
    const anyFrozen = Boolean(frozen.all || frozen.yield || frozen.finder || frozen.copy);
    const modePill = $("mode-pill");
    modePill.textContent = String(wallet.mode || y.mode || "paper").toUpperCase();
    modePill.classList.toggle("pill-live", wallet.mode === "live");
    const frozenPill = $("frozen-pill");
    frozenPill.textContent = anyFrozen ? "FROZEN" : "OPERATIONAL";
    frozenPill.className = `pill ${anyFrozen ? "pill-frozen" : "pill-muted"}`;
  }

  function renderYield(status, stands) {
    const y = status.yield || {};
    const pos = y.position;
    const best = y.best;
    const frozen = Boolean(y.frozen);

    setTag("yield-tag", frozen ? "FROZEN" : y.last_action || "ready", frozen ? "bad" : "ok");

    const poolRows = (stands && Array.isArray(stands.allowed) ? stands.allowed : [])
      .slice(0, 5)
      .map(
        (pool) => `
        <div class="row">
          <span class="sym">${esc(pool.project || "—")}</span>
          <span class="num">${compactUsd(pool.tvl_usd)} TVL</span>
          <span class="dir up">${apy(pool.apy)}</span>
        </div>`
      )
      .join("");

    $("yield-body").innerHTML = `
      <div class="kv"><span>Current position</span><strong>${pos ? esc(pos.project) : "Cash only"}</strong></div>
      <div class="kv"><span>Principal</span><strong>${pos ? usd(pos.amount_usd) : usd(y.cash_usd)}</strong></div>
      <div class="kv"><span>Position APY</span><strong class="${pos ? "up" : ""}">${pos ? apy(pos.apy) : "—"}</strong></div>
      <div class="kv"><span>Yield cash</span><strong>${usd(y.cash_usd)}</strong></div>
      <div class="kv"><span>Best available</span><strong>${best ? `${esc(best.project || "—")} · ${apy(best.apy)}` : "—"}</strong></div>
      <div class="list-title"><span>Allowlisted pools</span><span>${esc(stands && stands.source ? stands.source : y.source || "")}</span></div>
      ${poolRows ? `<div class="rows">${poolRows}</div>` : '<div class="empty">No allowlisted pools right now.</div>'}
      ${y.last_reason ? `<div class="empty">${esc(y.last_reason)}</div>` : ""}
    `;
  }

  function renderFinder(status, filters) {
    const f = status.finder || {};
    setTag(
      "finder-tag",
      `${Number(f.tracked_count || 0)} tracked`,
      Number(f.tracked_count || 0) > 0 ? "ok" : ""
    );

    const fmap = (filters && filters.filters) || {};
    const labels = {
      min_market_cap: "Min market cap",
      min_volume_24h: "Min volume 24h",
      min_txns_24h: "Min txns 24h",
      min_liquidity: "Min liquidity",
      max_age_hours: "Max age (h)",
      max_risk_score: "Max risk score",
      min_buy_pressure: "Min buy pressure",
      min_vol_liq_ratio: "Min vol/liq",
      max_top10_holder_pct: "Max top-10 %",
    };
    const filterRows = Object.keys(fmap)
      .map(
        (key) => `
        <div class="row">
          <span class="sym">${esc(labels[key] || key)}</span>
          <span class="num">${Number(fmap[key]).toLocaleString("en-US")}</span>
          <span class="dir flat">${key.startsWith("max_") && key.includes("pct") ? "%" : ""}</span>
        </div>`
      )
      .join("");

    $("finder-body").innerHTML = `
      <div class="kv"><span>Tracked mints</span><strong>${Number(f.tracked_count || 0)}</strong></div>
      <div class="kv"><span>Last scan</span><strong>${relTime(f.last_scan_at)}</strong></div>
      <div class="list-title"><span>Acceptance filters</span><span>value</span></div>
      ${filterRows ? `<div class="rows">${filterRows}</div>` : '<div class="empty">Filters unavailable.</div>'}
    `;
  }

  function renderCopy(status) {
    const c = status.copy || {};
    const wallets = c.wallets || {};
    const positions = c.positions || {};
    const addresses = Object.keys(wallets);
    setTag("copy-tag", `${addresses.length} wallets`, addresses.length ? "ok" : "");

    const walletRows = addresses
      .slice(0, 6)
      .map((address) => {
        const meta = wallets[address] || {};
        return `
        <div class="row">
          <span class="sym" title="${esc(address)}">${esc(meta.label || short(address))}</span>
          <span class="num">${relTime(meta.followed_at)}</span>
          <span class="dir flat">${short(address)}</span>
        </div>`;
      })
      .join("");

    const posCount = Object.keys(positions).length;
    const fillCount = Array.isArray(c.fills) ? c.fills.length : Array.isArray(c.recent_fills) ? c.recent_fills.length : 0;

    $("copy-body").innerHTML = `
      <div class="kv"><span>Followed wallets</span><strong>${addresses.length}</strong></div>
      <div class="kv"><span>Open positions</span><strong>${posCount}</strong></div>
      <div class="kv"><span>Recent fills</span><strong>${fillCount}</strong></div>
      <div class="kv"><span>Copy cash</span><strong>${usd(c.cash_usd)}</strong></div>
      <div class="list-title"><span>Wallets</span><span>address</span></div>
      ${walletRows ? `<div class="rows">${walletRows}</div>` : '<div class="empty">No wallets followed yet.</div>'}
    `;
  }

  function renderTrade(trade, markets) {
    if (!trade) {
      $("trade-body").innerHTML = '<div class="empty">Trade desk unavailable.</div>';
      setTag("trade-tag", "offline", "bad");
      return;
    }

    const unreal = Number(trade.unrealized_pnl_usd || 0);
    setTag("trade-tag", `${Number(trade.open_positions || 0)} positions`, Number(trade.open_positions || 0) ? "ok" : "");

    const marketRows = (markets || [])
      .slice(0, 8)
      .map((m) => {
        const change = Number(m.price_change_24h);
        return `
        <div class="row">
          <span class="sym" title="${esc(m.name || m.mint)}">${esc(m.symbol || short(m.mint))}</span>
          <span class="num">${usd(m.price_usd, 6)}</span>
          <span class="dir ${dirClass(change)}">${pct(change)}</span>
        </div>`;
      })
      .join("");

    $("trade-body").innerHTML = `
      <div class="kv"><span>Equity</span><strong>${usd(trade.equity_usd)}</strong></div>
      <div class="kv"><span>Cash</span><strong>${usd(trade.cash_usd)}</strong></div>
      <div class="kv"><span>Unrealized P&amp;L</span><strong class="${dirClass(unreal)}">${usd(unreal)}</strong></div>
      <div class="kv"><span>Realized P&amp;L</span><strong class="${dirClass(trade.realized_pnl_usd)}">${usd(trade.realized_pnl_usd)}</strong></div>
      <div class="list-title"><span>Markets</span><span>24h</span></div>
      ${marketRows ? `<div class="rows">${marketRows}</div>` : '<div class="empty">Market feed unavailable right now.</div>'}
    `;
  }

  function renderWallet(wallet) {
    if (!wallet) {
      $("wallet-body").innerHTML = '<div class="empty">Wallet unavailable.</div>';
      setTag("wallet-tag", "offline", "bad");
      return;
    }

    const desks = wallet.desks || {};
    const chain = wallet.chain || {};
    setTag("wallet-tag", wallet.live_enabled ? "LIVE" : "PAPER", wallet.live_enabled ? "warn" : "");

    const deskRows = ["yield", "trade", "copy"]
      .map((name) => {
        const d = desks[name] || {};
        return `
        <div class="row">
          <span class="sym">${esc(name)}</span>
          <span class="num">idle ${usd(d.idle_usd)}</span>
          <span class="dir flat">${usd(d.total_usd)}</span>
        </div>`;
      })
      .join("");

    const chainBits = [];
    if (chain.devnet_sol != null) chainBits.push(`devnet SOL ${Number(chain.devnet_sol).toFixed(4)}`);
    if (chain.devnet_usdc != null) chainBits.push(`devnet USDC ${Number(chain.devnet_usdc).toFixed(2)}`);
    if (chain.mainnet_sol != null) chainBits.push(`mainnet SOL ${Number(chain.mainnet_sol).toFixed(4)}`);
    if (chain.mainnet_usdc != null) chainBits.push(`mainnet USDC ${Number(chain.mainnet_usdc).toFixed(2)}`);

    const ledger = Array.isArray(wallet.ledger) ? wallet.ledger.slice(0, 4) : [];
    const ledgerRows = ledger
      .map(
        (entry) => `
        <div class="row">
          <span class="sym">${esc(entry.kind || "entry")}</span>
          <span class="num">${esc(entry.from)} → ${esc(entry.to)}</span>
          <span class="dir flat">${usd(entry.amount_usd)}</span>
        </div>`
      )
      .join("");

    $("wallet-body").innerHTML = `
      <div class="kv"><span>Hub cash</span><strong>${usd(wallet.cash_usd)}</strong></div>
      <div class="kv"><span>Idle</span><strong>${usd(wallet.idle_usd)}</strong></div>
      <div class="kv"><span>Deployed</span><strong>${usd(wallet.deployed_usd)}</strong></div>
      <div class="list-title"><span>Desks</span><span>total</span></div>
      <div class="rows">${deskRows}</div>
      ${chainBits.length ? `<div class="list-title"><span>Chain</span><span>balances</span></div><div class="empty">${esc(chainBits.join(" · "))}</div>` : ""}
      ${ledgerRows ? `<div class="list-title"><span>Ledger</span><span>amount</span></div><div class="rows">${ledgerRows}</div>` : ""}
    `;
  }

  function renderOps(frozen) {
    const state = frozen || {};
    const desks = ["all", "yield", "finder", "copy"];
    const anyFrozen = desks.some((desk) => Boolean(state[desk]));
    setTag("ops-tag", anyFrozen ? "frozen" : "armed", anyFrozen ? "bad" : "ok");

    $("ops-body").innerHTML = `
      <div class="ops-grid">
        ${desks
          .map((desk) => {
            const isFrozen = Boolean(state[desk]);
            return `
            <div class="ops-item">
              <div>
                <div class="name">${esc(desk)}</div>
                <div class="state">${isFrozen ? "frozen" : "running"}</div>
              </div>
              <button class="btn btn-sm ${isFrozen ? "" : "btn-danger"}"
                data-action="${isFrozen ? "thaw" : "freeze"}:${desk}">
                ${isFrozen ? "Thaw" : "Freeze"}
              </button>
            </div>`;
          })
          .join("")}
      </div>
      ${state.reason ? `<div class="empty">Reason: ${esc(state.reason)}</div>` : ""}
    `;
  }

  function markUpdated() {
    $("updated-at").textContent = new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }

  async function load({ quiet = false } = {}) {
    try {
      const [status, stands, filters, trade, markets] = await Promise.all([
        get("/status"),
        get("/yield/stands").catch(() => null),
        get("/finder/filters").catch(() => null),
        get("/trade/status").catch(() => null),
        get("/trade/markets?limit=8").catch(() => null),
      ]);

      if (trade) status.trade = trade;
      renderHero(status);
      renderYield(status, stands);
      renderFinder(status, filters);
      renderCopy(status);
      renderTrade(trade, markets && markets.markets ? markets.markets : []);
      renderWallet(status.wallet);
      renderOps(status.frozen);
      markUpdated();
      if (!quiet) toast("Desks refreshed");
    } catch (err) {
      if (!quiet) toast(err.message || "Refresh failed", true);
      console.error(err);
    }
  }

  async function runAction(button, action) {
    const label = button.textContent;
    button.disabled = true;
    try {
      if (action === "tick") {
        await post("/yield/tick");
        toast("Yield tick complete");
      } else if (action === "finder-scan") {
        const result = await post("/finder/scan");
        toast(`Finder scan: ${result && result.passed != null ? result.passed : 0} passed`);
      } else if (action === "copy-scan") {
        const result = await post("/copy/scan");
        toast(`Copy scan: ${result && result.replications_count != null ? result.replications_count : 0} signals`);
      } else if (action.startsWith("freeze:")) {
        const desk = action.split(":")[1];
        await post("/ops/freeze", { desk, reason: "frozen from web console" });
        toast(`Frozen ${desk}`);
      } else if (action.startsWith("thaw:")) {
        const desk = action.split(":")[1];
        await post("/ops/thaw", { desk });
        toast(`Thawed ${desk}`);
      }
      await load({ quiet: true });
    } catch (err) {
      toast(err.message || "Action failed", true);
    } finally {
      button.disabled = false;
      button.textContent = label;
    }
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-action]");
    if (!button) return;
    const action = button.dataset.action;
    if (action === "refresh") {
      load();
      return;
    }
    runAction(button, action);
  });

  $("follow-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const address = $("follow-address").value.trim();
    const label = $("follow-label").value.trim();
    if (!address) {
      toast("Enter a Solana wallet address", true);
      return;
    }
    const button = event.target.querySelector("button");
    button.disabled = true;
    try {
      await post("/copy/wallets", { address, label });
      $("follow-address").value = "";
      $("follow-label").value = "";
      toast("Wallet followed");
      await load({ quiet: true });
    } catch (err) {
      toast(err.message || "Could not follow wallet", true);
    } finally {
      button.disabled = false;
    }
  });

  $("quote-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const query = $("quote-input").value.trim();
    const box = $("quote-result");
    if (!query) {
      box.hidden = true;
      return;
    }
    box.hidden = false;
    box.textContent = "Looking up…";
    try {
      const item = await get(`/trade/quote?q=${encodeURIComponent(query)}`);
      const change = Number(item.price_change_24h);
      box.innerHTML = `
        <div class="row-head">
          <strong>${esc(item.symbol || "—")} <span class="num">${esc(item.name || "")}</span></strong>
          <span class="${dirClass(change)}">${pct(change)} 24h</span>
        </div>
        <div class="kv"><span>Price</span><strong>${usd(item.price_usd, 8)}</strong></div>
        <div class="kv"><span>Liquidity</span><strong>${compactUsd(item.liquidity_usd)}</strong></div>
        <div class="kv"><span>Market cap</span><strong>${compactUsd(item.market_cap)}</strong></div>
        <div class="kv"><span>Mint</span><strong class="mono-sm">${esc(short(item.mint, 6, 6))}</strong></div>
        ${item.chart_url ? `<div class="kv"><span>Chart</span><strong><a href="${esc(item.chart_url)}" target="_blank" rel="noopener">DexScreener ↗</a></strong></div>` : ""}
      `;
    } catch (err) {
      box.innerHTML = `<span class="down">${esc(err.message || "No market found")}</span>`;
    }
  });

  function start() {
    load({ quiet: true });
    clearInterval(timer);
    timer = setInterval(() => {
      if (!document.hidden) load({ quiet: true });
    }, REFRESH_MS);
  }

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) load({ quiet: true });
  });

  start();
})();
