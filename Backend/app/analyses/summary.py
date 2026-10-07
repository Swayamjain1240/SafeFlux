"""The after-evidence AI summary (Part 9).

The runner may ask a configured provider to *explain the evidence after the
evidence exists*. This module is the only place that touches the provider in
Part 9, and it is hard-gated: with no ``NEBIUS_*`` configuration it returns
``None`` and the run carries the explicit not-configured note instead.

Language discipline: the summarizer's own prompt quotes the required wording —
never "guaranteed safe", never "the real plant is unsafe" — and its output is
stored separately from the simulation evidence it stems from. The AI can be
wrong about *meaning*; it cannot change a value or a verdict.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from app.ai.provider import ProviderConfig, build_provider

logger = logging.getLogger("safeflux.analysis.summary")

SYSTEM_PROMPT = (
    "You are writing a short engineering note about process-safety simulation "
    "results for SafeFlux. You summarize evidence you are given; you never "
    "invent numbers, never add values that are not quoted to you, never relax a "
    "limit, and never issue a verdict. Use the exact required language: say "
    "'No unsafe condition was detected within the tested simulation scenarios.' "
    "when the evidence shows none, never claim a configuration is 'guaranteed "
    "safe', never claim a real plant safeguard is unsafe (times describe the "
    "modelled safeguard in the simulated scenario only). Keep under 180 words "
    "and refer only to the evidence provided."
)

MAX_EVIDENCE_CHARS = 6000


def _evidence_text(evidence: dict) -> str:
    """Compact, bounded JSON of just what the model may see."""
    import json

    payload = {
        "pivot": evidence.get("pivot"),
        "counterfactuals": evidence.get("counterfactuals"),
        "safeguards": evidence.get("safeguards"),
    }
    text = json.dumps(payload, default=str, allow_nan=False)
    return text[:MAX_EVIDENCE_CHARS]


def ai_summarizer_if_configured(settings) -> Callable[..., dict] | None:
    """Return the summarizer only when a provider is actually configured."""
    if not ProviderConfig.from_settings(settings).configured:
        return None
    provider = build_provider(ProviderConfig.from_settings(settings))

    def summarize(*, evidence: dict) -> dict:
        response = provider.complete(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _evidence_text(evidence)}],
            max_output_tokens=600,
        )
        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("provider returned an empty explanation")
        return {
            "text": text,
            "provider": getattr(provider, "name", "nebius"),
            "model_id": getattr(response, "model", ""),
            "tokens": getattr(response, "tokens", 0),
        }

    return summarize


__all__ = ["SYSTEM_PROMPT", "ai_summarizer_if_configured"]
