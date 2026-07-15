from __future__ import annotations

from ..domain.contracts import ConversationTurn, ProviderRequest, TestCase, ModelConfiguration
from ..util import sha256_hex


class PromptRenderer:
    VERSION = "we3.renderer.v1"

    def render(
        self,
        *,
        run_id: str,
        case: TestCase,
        model: ModelConfiguration,
        timeout_seconds: float = 60.0,
    ) -> ProviderRequest:
        messages: list[ConversationTurn] = []
        if case.conversation.system:
            messages.append(
                ConversationTurn(role="system", content=case.conversation.system)
            )
        messages.extend(case.conversation.turns)
        return ProviderRequest(
            run_id=run_id,
            model_config_id=model.model_config_id,
            provider=model.provider,
            model=model.model,
            messages=messages,
            parameters=model.parameters,
            timeout_seconds=timeout_seconds,
        )


def rendered_prompt_hash(request: ProviderRequest) -> str:
    return sha256_hex(
        {
            "renderer_version": PromptRenderer.VERSION,
            "messages": [message.model_dump(mode="json") for message in request.messages],
        }
    )
