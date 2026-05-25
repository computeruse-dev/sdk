# Computer Use Cloud — Engineering Spec

**Version**: 0.1 (draft, derived from the public claims on [computeruse.run](https://computeruse.run/))
**Status**: spec only. M0 (stub package + marketing site) is shipped; M1 onward is unbuilt.
**Owner**: TBD
**Last updated**: 2026-05-25

---

## TL;DR

We are building a managed cloud platform that lets developers run AI agents — specifically Anthropic Computer Use, OpenAI Operator, and Google Gemini agents — without provisioning their own sandbox infrastructure. The pitch on the homepage is:

1. **One Python (and later TS) SDK across all three providers.**
2. **Per-active-second billing** (the meter pauses while the model is thinking). 60% cheaper than Browserbase for typical agent workloads.
3. **~1.8s cold start** via a pre-warmed Chromium pool.
4. **Built-in live view URL**, residential proxy, captcha solving.
5. **Apache-2.0 open-source runtime** with a self-host path.

This document is the contract for what we have to build to make each of those claims true. Where a claim is non-trivial, we name the implementation approach and the open questions. Where a claim is aspirational (no decided answer), we say so.

---

## 1. Product surface

### 1.1 Python SDK (definitive surface — v0.1)

```python
from computeruse import Sandbox

# context-manager idiom
with Sandbox.claude(model="claude-sonnet-4-6") as sb:
    # low-level browser primitives
    sb.goto("https://www.google.com/flights")
    sb.screenshot()                  # bytes (PNG)
    sb.click(x=120, y=350)
    sb.type("San Francisco")

    # high-level agent loop
    result = sb.agent.run(
        "Find the cheapest direct flight SFO -> LIS next Tuesday. "
        "Return airline, price, and departure time."
    )

    print(result.value)              # final agent answer
    print(result.transcript)         # full step-by-step log
    print(result.usage.usd)          # cents spent on this run
    print(result.usage.active_seconds)
    print(result.live_view_url)      # public embeddable view of this session
```

Same shape for `Sandbox.openai(model="computer-use-preview")` and `Sandbox.gemini(model="gemini-3-agent")`.

**Why this shape:** mirrors `e2b_desktop.Sandbox` (the emerging convention) so existing Computer Use code ports with no learning curve, plus adds `sb.agent.run(...)` as the killer feature (collapses the ~40-line action loop into one call).

### 1.2 TypeScript SDK (v0.2, deferred)

```ts
import { Sandbox } from "computeruse";

await using sb = await Sandbox.claude({ model: "claude-sonnet-4-6" });
const result = await sb.agent.run("...");
```

`await using` requires Node 22+ / TypeScript 5.2+. Stub package on npm should ship in M2.

### 1.3 REST API (v0.1)

The SDK is a thin client over this surface. Anything the SDK does, a `curl` user can do.

| Verb | Path | Purpose |
|---|---|---|
| `POST` | `/v1/sandboxes` | Create sandbox. Body: `{provider, model, options}`. Returns: `{id, cdp_url, live_view_url}` |
| `GET` | `/v1/sandboxes/{id}` | State (`starting | ready | active | stopped`) |
| `POST` | `/v1/sandboxes/{id}/actions` | Dispatch a low-level action (click/type/screenshot/...) |
| `POST` | `/v1/sandboxes/{id}/agent/runs` | Run the high-level agent loop. SSE response stream. |
| `DELETE` | `/v1/sandboxes/{id}` | Stop sandbox |
| `GET` | `/v1/usage` | Active-second consumption + cost |

Auth: Bearer token (`Authorization: Bearer cu_…`). Issued per-account on signup.

### 1.4 CLI (v0.3, deferred)

`computeruse login` / `computeruse new` / `computeruse logs <id>` / `computeruse open <id>` (opens live view in browser). Nice-to-have.

---

## 2. Sandbox runtime

### 2.1 Container image

**Base**: Debian slim or Alpine, single-arch (amd64) for the first cut.

**Installed software**:

- Chromium (specific pinned version, updated weekly via dependabot-style PRs)
- Xvfb (headless display — needed even though Chromium can run headless, because Computer Use models expect a real X server for some interactions like drag-select)
- `xdotool` (synthesizes mouse/keyboard events when CDP can't)
- Common fonts (Noto CJK, Noto Color Emoji, Liberation, DejaVu)
- ffmpeg (for live view encoding)
- Python 3.11+ (for the in-sandbox agent process)
- `playwright` Python (drives the browser via CDP)

**Image size target**: <800 MB compressed, <2 GB uncompressed. Goal: fast pull on first launch in any new region.

### 2.2 Cold-start path

The 1.8s target on the homepage assumes a **pre-warmed pool**. Path breakdown:

| Step | Budget | What |
|---|---|---|
| Pool-pop | 100ms | Pluck a pre-warmed container from the warm pool, reassign network identity to the new tenant |
| Network attach | 200ms | Mount the per-tenant proxy + residential IP |
| Chromium boot (warm) | 400ms | Chromium is already running in the container; just navigate to `about:blank` |
| First action ready | 200ms | CDP handshake, accessibility tree initial snapshot |
| Total p50 | **0.9s** | Comfortable margin under 1.8s target |
| Cold cold-start (empty pool) | 4-6s | Pull image (if not cached), boot container, start Chromium |

The 1.8s claim is **p95**, not p50. P99 may hit 3s under traffic spikes; the pool warmer needs autoscaling.

**Open question:** sandbox isolation primitive. Options:
- (A) **Docker container, no kernel isolation** — fastest, weakest sandbox boundary. OK for trusted users, risky if we host untrusted code in the sandbox.
- (B) **gVisor** — user-mode kernel, stronger isolation, ~10-15% perf overhead.
- (C) **Firecracker microVM** — strongest, but ~500ms slower cold start. Used by Modal / E2B.

Recommendation: **A for M1, B by GA**. Compute Use agents are arbitrary-execution-grade risk; we need stronger than Docker for production.

### 2.3 Lifecycle states

```
                   create()
   not-existing  ─────────────►  starting  ──►  ready  ──►  active (per-action)
                                                  │             │
                                                  ▼             ▼
                                                idle────►stopped (TTL or explicit DELETE)
```

- `starting`: container booting + Chromium warming
- `ready`: idle, no action in-flight, **billing paused**
- `active`: action being dispatched OR model is being called with results, **billing running**
- `idle`: no action for >5s, returns to `ready`; container stays alive
- `stopped`: container reaped after inactivity TTL (default 5 min)

### 2.4 Resource limits per sandbox

| Resource | Default | Pro limit | Scale limit |
|---|---|---|---|
| vCPU | 2 | 4 | 8 |
| RAM | 4 GB | 8 GB | 16 GB |
| Disk (scratch) | 2 GB | 10 GB | 50 GB |
| Egress | 100 Mbps | 500 Mbps | 1 Gbps |
| Sandbox TTL (idle) | 5 min | 30 min | 24 hr |
| Max concurrent sandboxes per account | 5 | 25 | 250 |

### 2.5 Networking + egress

- Each sandbox gets a **per-tenant residential IP** rotated from a pool (vendor TBD — Bright Data, IPRoyal, or Oxylabs).
- Optional **sticky session** mode that pins the IP for the sandbox's lifetime (Pro feature).
- Egress whitelist: customers can blocklist or allowlist domains via API.

---

## 3. Model loop (per provider)

The unified abstraction is `sb.agent.run(prompt: str) -> AgentResult`. Internally, this dispatches to a provider-specific loop. The three loops are NOT identical — they differ in tool schemas, action types, and termination signals — but the SDK hides those differences.

### 3.1 Anthropic Computer Use

- API: `client.beta.messages.create(model=..., tools=[{"type": "computer_20241022", ...}], betas=["computer-use-2024-10-22"], messages=...)`
- Action types Claude returns: `screenshot`, `key`, `type`, `mouse_move`, `left_click`, `left_click_drag`, `right_click`, `middle_click`, `double_click`, `cursor_position`
- Termination: `stop_reason == "end_turn"` and no further tool calls
- Coordinate space: Claude expects width=1024, height=768 by default. We resize screenshots before sending.

### 3.2 OpenAI Operator (`computer-use-preview`)

- API: `client.responses.create(model="computer-use-preview", tools=[{"type": "computer_use_preview", ...}], input=...)`
- Action types: `click`, `double_click`, `drag`, `keypress`, `move`, `screenshot`, `scroll`, `type`, `wait`
- Termination: response stream completes without further `computer_call` items
- Coordinate space: native resolution; the model adapts.

### 3.3 Google Gemini agent

- API: `client.models.generate_content(model="gemini-3-agent", tools=[...], contents=...)` via Vertex AI or the consumer API.
- Action types: TBD (the Gemini agent action surface is still moving as of May 2026). Implementation deferred to M2/M3.
- **Honest note:** Gemini coverage may slip to M4 if the API stabilizes too late. The homepage and SDK should not block Claude+OpenAI shipping on Gemini being ready.

### 3.4 The unified `sb.agent.run()` abstraction

```python
class AgentResult:
    value: str                      # final answer (last assistant message)
    transcript: list[AgentStep]     # all model calls + actions
    usage: AgentUsage               # tokens, active_seconds, USD cost
    live_view_url: str
    error: Optional[AgentError]     # if the loop failed

class AgentStep:
    timestamp: datetime
    kind: Literal["thinking", "action", "observation"]
    payload: dict                   # provider-specific; serializable
```

`AgentResult` is identical across providers — the work of normalizing happens in the per-provider adapter.

**Implementation file layout:**

```
computeruse/
  __init__.py           # public Sandbox + Agent re-exports
  sandbox.py            # Sandbox class, low-level browser primitives
  agent.py              # Agent class, run() loop orchestration
  providers/
    base.py             # abstract Provider interface
    anthropic.py        # Claude Computer Use adapter
    openai.py           # Operator adapter
    gemini.py           # Gemini agent adapter
  _cdp.py               # CDP client wrapper
  _http.py              # REST client (talks to cloud control plane)
  _types.py             # Pydantic / dataclass models
```

---

## 4. Metering + billing

This is the deepest of the spec sections because the homepage's biggest claim ("60% cheaper than Browserbase") depends entirely on the metering being honest and verifiable.

### 4.1 What counts as "active"

A second is **active** iff at any point during it, the sandbox was doing one of:

- Executing a browser action (CDP call in flight: click, type, screenshot, navigate, etc.)
- Waiting on a browser response (page load, network idle, JS evaluation)
- Encoding a screenshot for the model

A second is **idle** (and not billed) iff the sandbox was:

- Waiting on the LLM API to return (the model is thinking)
- In `ready` state with no action queued

### 4.2 The metering pipeline

```
Sandbox action enters in-flight ──► meter_start(sandbox_id, ts)
Sandbox action completes        ──► meter_stop(sandbox_id, ts)
Model API call enters in-flight ──► meter_pause(sandbox_id, ts)
Model API call returns          ──► meter_resume(sandbox_id, ts)
```

Implementation:
- An in-sandbox metering daemon emits start/stop events to the control plane over a long-lived gRPC stream.
- The control plane aggregates into 1-second buckets per sandbox.
- Buckets are flushed to a billing database (Postgres or ClickHouse) every 5 minutes.
- The customer-facing usage API (`GET /v1/usage`) reads from the billing DB.

**Granularity**: 100ms resolution internally, billed at 1-second resolution (rounded up per call).

**Verifiability**: every `AgentResult.usage` carries the bucket breakdown (active vs paused vs idle) so customers can reproduce the meter from their side.

### 4.3 Plans + limits (as on the homepage, updated 2026-05-25)

| Plan | Price | Active hours included | Overage | Concurrency | Use case targeted |
|---|---|---|---|---|---|
| Free | $0 / month | 100 / month | hard stop | 5 sandboxes | E (individual dev, hackathon) |
| Pro | $20 / month | 500 / month | $0.01 / active hour | 25 sandboxes | A, B, C (RPA, scraping, QA) |
| Team | $200 / month | 5,000 / month | TBD | unlimited (fair use) | D (product backend) |

**Effective per-active-second prices:**
- Free: $0 (with hard stop at 100 hr)
- Pro included: $20 / (500 × 3600) = **$0.0000111/s ≈ $0.04/active-hour**
- Pro overage: $0.01 / 3600 = **$0.00000278/s** — cheaper than the included rate (see anomaly below)
- Team included: $200 / (5,000 × 3600) = **$0.0000111/s ≈ $0.04/active-hour**

The standard task (210 active seconds) on Pro included pricing costs about $0.0023 — well below the "$0.01 per standard task" headline. The headline number ($0.01) is a marketing round-up that gives us a buffer at lower volumes; the actual per-task price for Pro customers at high volume is closer to $0.002, which is even better.

### 4.4 The "10× cheaper than Browserbase" math (updated)

The vs/browserbase page now uses the **standard agent task** baseline:

> 10 minutes of browser uptime · 30 LLM decision steps · 1 CAPTCHA solve

Math:
- Browserbase: 10 min × $0.10/hr browser + $0.05 storage + $0.03 proxy + $0.003 CAPTCHA ≈ **$0.10**
- Us: 210 active seconds × $0.0000111/s (Pro included) ≈ $0.0023, rounded to **$0.01** for marketing simplicity (includes a buffer for low-volume customers below the included tier)
- Ratio: **~10× cheaper** for typical agent workloads. Sensible round number used across the site.
- For pure CDP scraping (100% active), the gap shrinks toward ~15% — site documents this honestly.

### 4.5 Open pricing anomaly to resolve

The Pro plan's **overage rate ($0.01/hour) is cheaper than the included rate ($0.04/hour)**. Most pricing structures have overage be more expensive than included, to incentivize predictable spend. The current structure incentivizes the opposite — buy Pro, then drive usage hard.

This is either:
- (a) intentional — a loyalty curve where heavy users pay less per unit
- (b) a typo in the original spec — should be $0.04 or $0.05 per overage hour

Recommendation: **change overage to $0.04/active-hour** (matches included rate, predictable). If we deliberately want loyalty pricing, we should price-test it explicitly.

---

## 5. Cold-start strategy

### 5.1 The pre-warmed pool

- Each region maintains a pool of `N` pre-warmed sandbox containers in `ready` state.
- Pool size auto-tunes to maintain `p95 cold start < 2s` over the trailing 5 minutes.
- Pool warmer is a control-plane process that watches the queue depth and runs `docker run` (or equivalent) ahead of demand.

### 5.2 1.8s p95 target

Reference numbers from E2B's published benchmarks suggest ~3-5s cold start without pre-warming, ~1s with. Our 1.8s p95 sits in between, achievable with a moderate pool size.

**Verification methodology** (must be in place before we publish this number with confidence):
- Synthetic probe: every minute, in every region, create a sandbox and measure time-to-first-action-acked.
- Publish the rolling p50/p95/p99 at `computeruse.run/status` (and reference from the homepage trust line).

### 5.3 Worst-case fallback

If the pool is empty under burst:
- Customer experiences cold cold-start: 4-6s.
- We bill from `ready` state regardless (i.e., cold start is on us, not the customer).

---

## 6. Live view URL

### 6.1 What it shows

A public read-only HTTPS page that displays the live Chromium contents of one sandbox. Includes:

- Live screen at ~15 FPS (sufficient for "watching an agent work"; not a video game).
- Real-time action overlay (a red dot at click coordinates, type events as captions).
- Action transcript scrolling below.

### 6.2 Implementation

- In-sandbox: `ffmpeg` captures the X display, encodes to VP9 / WebM, streams to a WebRTC SFU.
- Control plane: each sandbox's live view URL points to a short-lived signed URL at `live.computeruse.run/{token}`.
- Token expires when the sandbox stops; sandbox-creator can rotate or revoke.

### 6.3 Embedding

```html
<iframe src="https://live.computeruse.run/abc123"
        sandbox="allow-scripts" referrerpolicy="no-referrer"
        style="width:100%; aspect-ratio: 16/9;"></iframe>
```

Customer apps embed the live view to give end-users visibility into their own agent runs.

---

## 7. Migration shims (the comparison table promises)

### 7.1 Plain Playwright (CDP) compatibility

Customers connecting via Playwright's `connect_over_cdp(wss://...)` work with zero changes after swapping the connection URL.

**Implementation**: the cloud control plane exposes a CDP-compliant WebSocket gateway at `wss://connect.computeruse.run/{sandbox_id}?apiKey=...`. Internally proxies to the sandbox's local Chromium CDP port.

### 7.2 Stagehand compatibility (`@computeruse/stagehand`)

Stagehand's SDK has a pluggable `env` field (`LOCAL` / `BROWSERBASE`). We add `COMPUTERUSE` as a third option.

**Implementation**: fork `@browserbasehq/stagehand`, patch the env detection to route `COMPUTERUSE` traffic to our CDP gateway. Publish as `@computeruse/stagehand`. Track upstream Stagehand releases (likely via subtree merge weekly).

### 7.3 Browserbase Sessions API shim

Browserbase has a higher-level `bb.sessions.create()` API that wraps Playwright session lifecycle. We need a thin compat shim:

```python
from browserbase_compat import Browserbase     # our shim
bb = Browserbase(api_key=CU_API_KEY)            # reads our key
session = bb.sessions.create()                  # creates a CU sandbox
browser = playwright.chromium.connect_over_cdp(session.connectUrl)
```

`session.connectUrl` returns our CDP URL. `session.id` is mapped 1:1 to our sandbox ID.

---

## 8. Open source surface

### 8.1 What's Apache-2.0

- The **SDK** (`computeruse` PyPI package, `@computeruse/sdk` npm package): Apache-2.0. This is what's in `~/git/sdk`.
- The **runtime** (`computeruse-dev/runtime`): the sandbox container image source — Dockerfile, in-sandbox metering daemon, CDP/Playwright wrappers, the per-provider agent loops. Apache-2.0. **Not yet built.**
- The **migration shims** (`@computeruse/stagehand`, `browserbase_compat`): Apache-2.0.

### 8.2 What's closed

- The cloud orchestration layer (pool warmer, control plane, billing pipeline).
- The web dashboard (sign-up, key management, usage analytics).
- The pricing engine.

This is the standard "OSS engine + closed orchestration" split (HashiCorp, Sentry, GitLab CE/EE pre-pivot).

### 8.3 Self-host story

A user can:
1. Clone `computeruse-dev/runtime`.
2. `docker run computeruse/runtime` on their own infra.
3. Point the SDK at `wss://their-self-hosted-endpoint`.

What they GIVE UP by self-hosting:
- The pre-warmed pool (their cold start = always 4-6s).
- The hosted billing/metering pipeline (DIY).
- The captcha solver + residential proxy (DIY contracts with vendors).
- The live view URL (works, but they host the WebRTC SFU themselves).

This is fine. The cloud is for teams who would rather pay than maintain. The self-host path keeps us OSS-honest and gives the open-source flywheel its reason to exist.

---

## 9. Phased roadmap (realistic)

| Milestone | Scope | Estimate (solo dev, no other work) | Status |
|---|---|---|---|
| **M0** | Marketing site + stub SDK package + this spec | 1 week | **shipped 2026-05-25** |
| **M1** | Local single-sandbox prototype: Docker container with Chromium + Playwright + Claude Computer Use loop, no cloud, no billing. `python -m computeruse.dev claude "find me lisbon flights"` works on a laptop. | 2-3 weeks | not started |
| **M2** | Unify Claude + OpenAI behind `sb.agent.run()`. Add Gemini if Vertex agent API is stable; defer otherwise. Publish `computeruse==0.1.0` (no longer just a preview stub). | 3-4 weeks | not started |
| **M3** | Cloud orchestration: control plane, pool warmer, CDP gateway, per-tenant sandboxes on Fly.io or Modal. p95 cold start measurement in place. | 4-6 weeks | not started |
| **M4** | Live view URL + per-active-second metering + billing pipeline + sign-up + Stripe integration. | 6-8 weeks | not started |
| **M5** | Public beta. Real customers. Open `computeruse-dev/runtime` repo. Publish `@computeruse/stagehand` migration shim. | + 4 weeks | not started |
| **GA** | SOC 2 Type I in audit, p95 cold start verified live, ten customers in production. | + 6-8 weeks | not started |

Total from M1 → GA: realistically **4-6 months solo, 2-3 months with a co-founder + 1 engineer**.

---

## 10. Open questions / unknowns

1. **Metering rate vs Pro plan rate are inconsistent on the public site.** $0.000333/s in the comparison table ≠ $0.000056/s implied by the Pro plan math. Reconcile.
2. **"60% cheaper" claim** is 78% on the stated scenario; either tighten the wording or change the scenario. Either is fine — but ship with consistent numbers.
3. **Sandbox isolation primitive** for M1: Docker (cheap), gVisor (safer), Firecracker (safest). Recommendation A→B by GA.
4. **Residential proxy vendor**: Bright Data is the safe pick; IPRoyal / Oxylabs are cheaper. Decide before pricing changes.
5. **Captcha solving vendor**: 2Captcha is the cheapest; CapSolver has better hCaptcha solve rates. Decide before M4.
6. **Gemini agent API stability**: if Vertex's agent API is still moving when we ship M2, we ship Claude+OpenAI only and add Gemini in M3/M4.
7. **Where does the cloud actually run**: Fly.io (cheap, regional, easy), Modal (same DNA — also a sandbox cloud — possible vendor risk), AWS Fargate (expensive, polished), self-managed K8s (cheapest, ops cost). Decide before M3.
8. **The Anthropic / OpenAI hosted Computer Use risk**: both vendors will likely ship first-party hosted Computer Use within 12-18 months. Our hedge: multi-provider SDK, Apache-2.0 runtime, faster cold start, cheaper.
9. **`browserbase_compat` shim legal posture**: re-implementing the BB Sessions API surface for compat is fine; copying their code is not. Audit before shipping.
10. **Stripe vs Polar vs Lemon Squeezy** for billing in M4. Polar is OSS-friendly and cheaper; Stripe is the safe pick.

---

## 11. Non-goals (explicit)

To prevent scope creep, we are NOT building:

- Our own LLM or model hosting (bring-your-own-key for the model providers).
- A no-code agent builder UI.
- High-level agent frameworks (LangChain / CrewAI / AutoGen are downstream of us, not competitors).
- A browser extension or desktop app.
- Mobile-device automation (no Android/iOS sandboxes in scope).
- A scraping product (we are infra for agents; scrapers can use us, but we don't market to scrapers).
- A web crawler / search index (compete with Firecrawl, Exa, etc. — different category).

---

## 12. References

- **Anthropic Computer Use docs**: <https://docs.anthropic.com/en/docs/build-with-claude/computer-use>
- **OpenAI Operator (computer-use-preview)**: <https://platform.openai.com/docs/guides/tools-computer-use>
- **E2B Desktop**: <https://github.com/e2b-dev/desktop> (the convention we're borrowing)
- **Browserbase pricing** (comparison baseline): <https://www.browserbase.com/pricing>
- **Stagehand**: <https://github.com/browserbase/stagehand>
- **Marketing site** (the public claims this spec backs): <https://computeruse.run/>
- **vs Browserbase comparison**: <https://computeruse.run/vs/browserbase.html>

---

## Appendix A — Inconsistencies between marketing copy and this spec

Updated 2026-05-25 after the use-case-first IA pivot.

**Resolved (no longer marketing risks):**

- ~~Pricing rate mismatch~~ — reconciled. New Pro/Team rate is $0.0000111/s (≈ $0.04/hour). Standard task headline ($0.01) is a marketing round-up that builds in buffer.
- ~~"60% cheaper" claim~~ — replaced everywhere with "~10× cheaper on a standard agent task" backed by transparent math.
- ~~Free tier amount~~ — bumped from 10 to 100 active hours/month; consistent across homepage, FAQ, JSON-LD, and SDK README.

**Still open:**

1. **Pro overage rate is cheaper than included rate** (see §4.5). Recommend changing overage from $0.01/hour to $0.04/hour to match the included rate.
2. **"2-second cold start"** is a p95 claim, but the homepage presents it as typical. Either qualify in copy ("p95 1.8s") or commit to making it the median.
3. **`computeruse-dev/runtime` repo doesn't exist yet** — homepage footer and SDK README both link to it. Either create the empty repo now with a stub README, or soften to "runtime · open-sourcing in M5".
4. **Standard task definition** is now consistent across homepage, all three /vs/ pages, and this spec: 10 min browser + 30 LLM steps + 1 CAPTCHA solve. Make sure new copy doesn't drift from this baseline — every pricing claim should be referenceable back to it.
5. **Browserbase Sessions API compatibility** is claimed across the homepage and the /vs/browser-use page. The shim package (`computeruse.browserbase_compat`) is sketched in the SDK but not yet implemented. Either build a minimal shim in the M1-M2 window, or remove the claim from the homepage until M3.

These are not bugs — they're the gap between marketing and engineering reality that the spec exists to close.
