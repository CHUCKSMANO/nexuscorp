# The Token Yielder

This is the paper-mode loop from our plan:

Scout reads rates → Treasurer applies rules → Runner updates a fake portfolio → Scribe logs it.

No real money moves until you later change `MODE=paper`. Leave it on paper.

## What you will have after tonight

- Python tools on your Mac
- This project running
- One live read of Solana USDC lending rates
- A simulated $10,000 portfolio that can “rebalance” on screen

---

## Phase 0 — tools on the Mac (do this first)

Open **Terminal**. Copy each block, press Return, wait until it finishes.

### 0.1 Install Homebrew if you do not have it

```bash
which brew || /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Apple Silicon Macs then need this once:

```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

### 0.2 Install Python 3

```bash
brew install python
python3 --version
```

You want 3.11 or newer.

### 0.3 Optional but useful later: Solana CLI

Skip this tonight if you want. You only need it when we touch a real wallet.

```bash
sh -c "$(curl -sSfL https://release.anza.xyz/stable/install)"
echo 'export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
solana --version
```

---

## Phase 1 — put this project on your Mac

1. Download `agentics.zip` from this chat.
2. Unzip it. A good place:

```bash
mkdir -p ~/Projects
unzip ~/Downloads/agentics.zip -d ~/Projects
cd ~/Desktop/nexuscorp
```

3. Create a private settings file:

```bash
cp .env.example .env
```

4. Create a virtual environment (an isolated Python box):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Your prompt should now start with `(.venv)`.

---

## Phase 2 — run one paper tick

```bash
cd ~/Desktop/nexuscorp
source .venv/bin/activate
python loop.py
```

You should see something like:

```
mode=paper  interval=3600s
allowlisted USDC pools: N
best: jupiter-lend  5.xx%  TVL $...
decision: rebalance — move $9800.00 from cash 0.00% -> jupiter-lend 5.xx%
```

Then open:

```bash
cat state/paper_portfolio.json
```

That file is your fake wallet. First tick usually moves the simulated $10,000 into the best allowlisted USDC pool.

Run it again:

```bash
python loop.py
```

Second tick should say **hold**, unless a different allowlisted pool is at least 0.40% better.

Watch mode (leave it running):

```bash
python loop.py --watch
```

Stop with `Control + C`.

---

## Phase 3 — read the rules so you trust them

Open `config.py`.

- `ALLOWLIST_PROJECTS` — only kamino-lend, jupiter-lend, save
- `ALLOWLIST_SYMBOLS` — only USDC
- `MIN_EDGE_APY = 0.40` — do not move for tiny differences
- `MIN_MOVE_USD = 200`
- `GAS_BUFFER_USD = 200` — keep a buffer un-deployed

The Treasurer cannot invent a new protocol. If Scout sees a 200% meme pool, it is ignored.

---

## Phase 4 — Telegram ping (optional)

1. In Telegram, search `@BotFather`, send `/newbot`, copy the token.
2. Search `@userinfobot`, copy your chat id.
3. Put both in `.env`:

```
TELEGRAM_BOT_TOKEN=123:abc
TELEGRAM_CHAT_ID=123456789
```

4. Run `python loop.py` again. You only get a message when it rebalances.

---

## Phase 5 — real Solana wallet, still no spending

```bash
solana-keygen new --outfile ~/.config/solana/paper.json
solana-keygen pubkey ~/.config/solana/paper.json
solana config set --url https://api.devnet.solana.com
solana airdrop 2
solana balance
```

Paste the public key into `.env` as `WALLET_PUBKEY=...`

Do **not** put the JSON key file inside this project folder. Do **not** screenshot it. Do **not** email it.

Create a free Helius key at https://helius.dev and set:

```
RPC_URL=https://mainnet.helius-rpc.com/?api-key=YOUR_KEY
```

Mainnet RPC is only for reading prices/balances. The runner is still locked.

---

## Phase 6 — live mode (later, tiny size)

Do not do this tonight.

When we get here together:

1. You fund a **dedicated** wallet with an amount you can lose ($50–$200 first).
2. We add a real deposit instruction for one allowlisted market only.
3. `MODE` stays `paper` until that instruction is tested on devnet.
4. Then `MODE=live` with a hard cap in code.

The current `runner.py` will refuse live mode on purpose.

---

## Discord frontend

The Discord command deck lives in `~/Desktop/nexuscorpbot`. It talks to this backend over HTTP (`NEXUS_API_URL`, default `http://127.0.0.1:8000`). Start the API first (`python app.py`), then `./agentics.sh bot-start` or `npm start` in the bot folder.

## Native macOS app (Xcode)

The Python backend also has a SwiftUI desktop terminal in `NexusApp`, with the
shared model layer and API client in the `NexusCore` framework.

```bash
pip install -r requirements-dev.txt   # pytest, for the Python suite
make build                            # Debug build for macOS arm64
make test                             # Swift unit tests
make run                              # build and open NexusCorp.app
```

Or open `NexusCorp.xcodeproj` in Xcode and run the `NexusCorp` scheme.
`project.yml` is the source of truth — edit it, then `make generate`.

Start the backend first (`python app.py`); the app polls `127.0.0.1:8000` and
can start the backend for you from the Ops desk.

### Two things that will bite you again

**Derived data must not live on the Desktop.** `~/Desktop` is a File Provider
volume that re-injects `com.apple.FinderInfo` on directories it syncs, and
ad-hoc codesign rejects the result with `resource fork, Finder information, or
similar detritus not allowed`. The `Makefile` points `-derivedDataPath` at
`~/Library/Developer/NexusCorpDerivedData` for this reason. If you build with a
different derived data path and hit that error, this is why.

**`NexusAppTests` must not have a `TEST_HOST`.** The tests are pure model
decoding and URL building, so they link `NexusCore` directly. When they were
app-hosted, launching the bundle booted the whole SwiftUI app, whose
`bootstrap()` spawned the Python backend and hammered the network — the test
runner never finished connecting and the suite hung for 366s before failing.

### Backend event loop

`agents/scribe.py` uses blocking `requests` for Telegram and Discord. Calling it
directly from an `async def` stalls the entire uvicorn event loop, so every
endpoint queues behind it. All such calls are wrapped in `asyncio.to_thread` —
keep it that way when adding alert channels. The tokens are currently blanked in
`.env` (bots deactivated), which makes `scribe.telegram` / `scribe.discord`
return immediately.

---

## Daily habit

1. Activate the venv: `source ~/Desktop/nexuscorp/.venv/bin/activate`
2. `python loop.py`
3. Read `state/paper_portfolio.json` and `logs/loop.jsonl`

Yield on paper is a calculator: `$amount × APY / 365`. Real yield starts the day real USDC is deposited, which is Phase 6.

## Safety

- `.env` stays on your Mac only
- Never paste a secret key into this chat
- Paper portfolio is not money
- Allowlist exists so the agent cannot farm a 8,000% LP
