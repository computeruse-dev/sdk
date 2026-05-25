# computeruse

**Computer Use Cloud — the cloud browser for AI agents. Drop-in compatible with Anthropic Computer Use, Browser Use SDK, and Browserbase Session API.**

> **Preview release.** The hosted API is not live yet. This package reserves the name and ships the planned SDK shape so you can prototype against it. Join the waitlist at [computeruse.run](https://computeruse.run/).

## Three compatibility modes

Pick the one that matches the code you already have:

### 1. Claude Computer Use mode

Your Claude code is unchanged. The Anthropic `computer_20241022` tool schema stays exactly the same. Only the execution backend swaps — from the self-hosted Docker that Anthropic's reference implementation expects you to run, to a managed sandbox on us.

```python
from computeruse import Sandbox

with Sandbox.claude(model="claude-sonnet-4-6") as sb:
    result = sb.agent.run(
        "File this insurance claim. Form is at acmehealth.example/claims/new."
    )
    print(result.transcript)
```

### 2. Browser Use / Playwright / CDP mode

Any client that speaks Chrome DevTools Protocol works out of the box: Browser Use SDK, Playwright, Puppeteer, Selenium-CDP, Stagehand. Point the connection URL at us and the rest of your script is unchanged.

```python
# Same Browser Use SDK code you already have.
from browser_use import Agent
import asyncio, os

agent = Agent(
    task="Find the cheapest direct flight to Lisbon next Tuesday.",
    cdp_url=os.environ["CU_CDP_URL"],  # wss://connect.computeruse.run?apiKey=...
)
asyncio.run(agent.run())
```

### 3. Browserbase Session API mode

If you already use Browserbase's `sessions.create()` surface, swap one base URL. Session lifecycle, recording, and live view all behave the same way.

```python
# Drop-in compatible with Browserbase's SDK shape.
from computeruse.browserbase_compat import Browserbase

bb = Browserbase(api_key=CU_API_KEY)            # reads our key
session = bb.sessions.create()                  # creates a CU sandbox
browser = playwright.chromium.connect_over_cdp(session.connectUrl)
```

## What it does today

Currently, calling any `Sandbox.*` method raises `computeruse.PreviewError` with a link to the waitlist. The package exists to (a) reserve the name on PyPI, (b) publish the planned SDK shape so you can read it, type-check against it, and prepare migrations.

```python
>>> from computeruse import Sandbox
[computeruse] Preview package. The hosted Computer Use Cloud API is not live yet.
             Calling Sandbox.claude() / .openai() / .gemini() will raise PreviewError.
             Join the waitlist: https://computeruse.run/

>>> Sandbox.claude()
computeruse.PreviewError: computeruse is in private preview. ...
```

Silence the import banner with `COMPUTERUSE_QUIET=1`.

## Status

| Component | Status |
|---|---|
| Website | Live · [computeruse.run](https://computeruse.run/) |
| Python SDK shape | Published (this package) |
| Hosted API | Private preview |
| Apache-2.0 runtime | Coming (M3-M4) |

See [SPEC.md](SPEC.md) for the engineering contract — the per-provider model loops, the sandbox runtime, the metering pipeline, the migration shims, and the phased roadmap.

## Why this exists

Running an AI agent in production today means picking one of these unpleasant trade-offs:

- **Anthropic Computer Use path.** You get the model but you build the browser cluster, the screenshot loop, the IP rotation, the CAPTCHA contract, the ops. Most teams burn an engineer-month on infra they didn't want to build.
- **Browser Use Cloud.** Great SDK, but three meters stacked (browser-time + LLM step + per-task) make the bill unpredictable on long-running agents.
- **Browserbase.** Production-polished but per-browser-hour billing, and Computer Use is "wire it yourself" because their abstraction is generic browser automation.
- **Self-host Playwright.** Cheap at the compute layer, expensive in ops time. No AI decision layer; no built-in CAPTCHA, residential IP, or live view URL.

Computer Use Cloud picks all four up at once: one SDK, three providers (Claude, OpenAI, Gemini), per-active-second billing, CAPTCHA + residential IP + live view included, Apache-2.0 runtime if you'd rather self-host.

[Read the full pitch →](https://computeruse.run/)
[How we compare to Anthropic →](https://computeruse.run/vs/anthropic-computer-use.html)
[How we compare to Browser Use →](https://computeruse.run/vs/browser-use.html)
[How we compare to Browserbase →](https://computeruse.run/vs/browserbase.html)

## License

Apache-2.0. See [LICENSE](LICENSE).

## Links

- Homepage: <https://computeruse.run/>
- Waitlist: <https://computeruse.run/#signup>
- Source: <https://github.com/computeruse-dev/sdk>
- Engineering spec: [SPEC.md](SPEC.md)
- Publish flow: [PUBLISHING.md](PUBLISHING.md)
