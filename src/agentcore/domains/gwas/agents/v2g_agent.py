"""V2G Agent -- Stage 1: format_gwas -> COJO -> SuSiE."""

from __future__ import annotations

import json
from typing import Any, Callable

from agentcore import state
from ..prompts.v2g import SYSTEM_PROMPT
from agentcore.providers import ANTHROPIC_MODEL_DEFAULT, OPENAI_MODEL_DEFAULT, make_provider
from ..tools import V2G_TOOLS, dispatch

MAX_ITERATIONS = 60
_LABEL = "V2G"


def run(
    *,
    run_id: str,
    context: dict[str, Any],
    provider_name: str = "anthropic",
    api_key: str = "",
    model: str | None = None,
    base_url: str | None = None,
    effort: str = "high",
    auto_approve: bool = True,
    emit_fn: Callable[..., None] | None = None,
) -> str:
    _model = model or (ANTHROPIC_MODEL_DEFAULT if provider_name == "anthropic" else OPENAI_MODEL_DEFAULT)
    _emit = emit_fn or (lambda **_: None)

    provider = make_provider(
        provider_name, api_key=api_key, model=_model,
        system_prompt=SYSTEM_PROMPT, base_url=base_url, effort=effort, tools=V2G_TOOLS,
    )

    initial = (
        f"Run the V2G stage for run '{run_id}'.\n\n"
        f"Context from the Planner:\n{json.dumps(context, indent=2)}\n\n"
        f"Checkpoint so far:\n{state.summarize_state(run_id)}\n\n"
        "Begin by calling read_checkpoint, then proceed step by step."
    )
    provider.send_user_text(initial)
    state.append_log(run_id, {"event": "v2g_start", "context": context})
    _emit(type="system", text="V2G stage started", agent=_LABEL)

    final_text = ""
    for _ in range(MAX_ITERATIONS):
        result = provider.step()
        if result.thinking:
            _emit(type="thinking", text=result.thinking, agent=_LABEL)
        if result.text:
            final_text = result.text
            _emit(type="text", text=result.text, agent=_LABEL)
        if result.stop_reason != "tool_use":
            break
        tool_results = []
        for call in result.tool_calls:
            _emit(type="tool_call", name=call["name"], input=call["input"], agent=_LABEL)
            try:
                output = dispatch(run_id, call["name"], call["input"], auto_approve, phase="v2g")
                is_error = bool(isinstance(output, dict) and output.get("error"))
            except Exception as exc:  # noqa: BLE001
                output = {"error": f"{type(exc).__name__}: {exc}"}
                is_error = True
            _emit(type="tool_result", name=call["name"], output=output, is_error=is_error, agent=_LABEL)
            tool_results.append({
                "tool_use_id": call["id"],
                "content": json.dumps(output, default=str),
                "is_error": is_error,
            })
        provider.send_tool_results(tool_results)

    state.append_log(run_id, {"event": "v2g_end", "summary": final_text[:500]})
    _emit(type="system", text="V2G stage complete", agent=_LABEL)
    return final_text
