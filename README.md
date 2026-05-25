# computeruse

**Computer Use Cloud — pre-configured cloud sandboxes for Claude, GPT, and Gemini Computer Use agents.**

> **Preview release.** The hosted API is not live yet. This package reserves the name and gives the planned SDK shape so you can prototype against it. Join the waitlist at [computeruse.run](https://computeruse.run/).

## What it does (planned)

Pre-configured Chromium sandboxes for running Anthropic Computer Use, OpenAI Operator, and Google Gemini agents — behind a single API, billed per active second.

```python
from computeruse import Sandbox

with Sandbox.claude(model="claude-sonnet-4-6") as sb:
    result = sb.run(
        "Find the cheapest direct flight to Lisbon next Tuesday."
    )
    print(result.transcript)
```

Swap providers with one line:

```python
with Sandbox.openai() as sb: ...
with Sandbox.gemini() as sb: ...
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
| Website | Live — [computeruse.run](https://computeruse.run/) |
| Python SDK shape | Published (this package) |
| Hosted API | Private preview |
| Apache-2.0 runtime | Coming |

## Why this exists

Running Anthropic Computer Use or OpenAI Operator in production today means:

- Writing a ~40-line action loop per model (and rewriting it when you swap providers, because Claude's `computer_20241022` and OpenAI's `computer-use-preview` use different tool schemas).
- Managing a sandbox container (E2B Desktop, self-hosted Docker, or wrapping Browserbase).
- Paying per browser-hour even while the model is thinking.

Computer Use Cloud collapses all of that into `with Sandbox.claude() as sb: sb.run(...)`. Pay per active second; idle is free.

[Read the full pitch →](https://computeruse.run/)
[How we compare to Browserbase →](https://computeruse.run/vs/browserbase.html)

## License

Apache-2.0. See [LICENSE](LICENSE).

## Links

- Homepage: <https://computeruse.run/>
- Waitlist: <https://computeruse.run/#signup>
- Source: <https://github.com/computeruse-dev/sdk>
- vs Browserbase: <https://computeruse.run/vs/browserbase.html>
