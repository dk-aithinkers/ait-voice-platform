"""Anthropic dialog provider.

The vendor SDK is imported inside this module and nowhere else — that is the
provider boundary constraint C-T1 requires. Nothing outside ``providers/``
knows this vendor exists.

**PHI handling.** Conversation history is PHI: transcripts are protected health
information by content, and the caller's voice is itself a listed identifier.
This provider unwraps PHI to build the request and re-wraps the response. Those
``reveal()`` calls are the sanctioned crossing point — the request goes to a
vendor that must hold an executed BAA before it may process a US tenant's audio
(constraint C-R1), which is why :meth:`respond` checks the tenant's jurisdiction
before sending anything.
"""

from __future__ import annotations

import os

from ait_voice.core.types import PHI, TenantContext, Utterance


class BAANotConfirmedError(RuntimeError):
    """Raised when PHI would reach a vendor without a confirmed BAA.

    Constraint C-R1: a BAA does not flow down to subcontractors, so every vendor
    touching call audio, transcripts or caller identity needs its own. One gap
    breaks the chain. This check is the enforcement point that rule otherwise
    lacks — the security review noted a Hard constraint with no build-time check
    is the weakest form it can take.
    """


class AnthropicLLM:
    """Dialog turns via the Anthropic Messages API."""

    name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 150,
        baa_confirmed: bool = False,
    ) -> None:
        """
        Args:
            baa_confirmed: Whether an executed BAA covers this vendor for PHI.
                Defaults to False so a US tenant cannot reach a vendor whose
                BAA nobody has confirmed. Set from the BAA register, never
                hardcoded to True.
        """
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self._model = model
        self._max_tokens = max_tokens
        self._baa_confirmed = baa_confirmed
        self._client = None

    def _get_client(self):  # noqa: ANN202 - vendor type stays inside the boundary
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client

    async def respond(
        self,
        tenant: TenantContext,
        history: list[Utterance],
        *,
        system_prompt: str,
    ) -> Utterance:
        if tenant.is_phi_jurisdiction and not self._baa_confirmed:
            raise BAANotConfirmedError(
                f"tenant {tenant.tenant_id!r} is in a PHI jurisdiction and no BAA "
                f"is confirmed for provider {self.name!r}; refusing to send transcript"
            )

        # Alternating caller/agent turns. The pipeline appends the caller's
        # utterance then the agent's reply, so parity gives the role.
        messages = [
            {
                "role": "user" if i % 2 == 0 else "assistant",
                "content": u.text.reveal(),
            }
            for i, u in enumerate(history)
        ]

        client = self._get_client()
        response = await client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system_prompt,
            messages=messages,
        )

        text = "".join(block.text for block in response.content if block.type == "text")
        return Utterance(text=PHI(text.strip()), is_final=True)
