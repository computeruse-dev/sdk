"""Computer Use Cloud — pre-configured cloud sandboxes for Claude, GPT, and Gemini Computer Use agents.

Preview release. The hosted API is not live yet. This package reserves the name
and gives the planned SDK shape so you can prototype against it.

Join the waitlist: https://computeruse.run/

Planned usage (once the hosted API is live):

    from computeruse import Sandbox

    with Sandbox.claude(model="claude-sonnet-4-6") as sb:
        result = sb.run("Find the cheapest direct flight to Lisbon next Tuesday.")
        print(result.transcript)

Swap providers with one line:

    with Sandbox.openai() as sb: ...
    with Sandbox.gemini() as sb: ...
"""

import os
import sys

__version__ = "0.0.1"
__all__ = ["Sandbox", "PreviewError"]

_BANNER = (
    "[computeruse] Preview package. The hosted Computer Use Cloud API is not live yet.\n"
    "             Calling Sandbox.claude() / .openai() / .gemini() will raise PreviewError.\n"
    "             Join the waitlist: https://computeruse.run/"
)


def _print_banner() -> None:
    if os.environ.get("COMPUTERUSE_QUIET"):
        return
    print(_BANNER, file=sys.stderr)


class PreviewError(RuntimeError):
    """Raised when a Sandbox method is called before the hosted API is live."""


class _PreviewSandbox:
    """Placeholder returned by Sandbox.* until the hosted API ships."""

    def __init__(self, provider: str, **kwargs):
        self._provider = provider
        self._kwargs = kwargs
        raise PreviewError(
            f"computeruse is in private preview. "
            f"Sandbox.{provider}({', '.join(f'{k}={v!r}' for k, v in kwargs.items())}) "
            f"will be callable once the hosted API is live. "
            f"Join the waitlist at https://computeruse.run/ to be notified."
        )


class Sandbox:
    """A managed Computer Use sandbox.

    Once the hosted API ships, instantiating a sandbox returns a context manager
    that gives you a pre-configured Chromium environment with the model's
    Computer Use loop already wired (screenshot capture, action dispatch, tool
    schema, retries, residential proxy, captcha solving, live view URL).

    Currently raises :class:`PreviewError` — see https://computeruse.run/.
    """

    @classmethod
    def claude(cls, *, model: str = "claude-sonnet-4-6", **kwargs):
        """Anthropic Computer Use sandbox. Preview-only."""
        return _PreviewSandbox("claude", model=model, **kwargs)

    @classmethod
    def openai(cls, *, model: str = "computer-use-preview", **kwargs):
        """OpenAI Operator sandbox. Preview-only."""
        return _PreviewSandbox("openai", model=model, **kwargs)

    @classmethod
    def gemini(cls, *, model: str = "gemini-3-agent", **kwargs):
        """Google Gemini agent sandbox. Preview-only."""
        return _PreviewSandbox("gemini", model=model, **kwargs)


_print_banner()
