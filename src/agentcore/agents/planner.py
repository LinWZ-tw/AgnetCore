"""Planner Agent -- Layer 1: inspect input, detect domain, present a plan,
dispatch bio workers or gwas stages, then call the Reporter.

A single Planner serves both domains. It is given both domains' input-
inspection tools (`inspect_data_source` for WES/scRNA, `inspect_gwas_input`
for GWAS summary stats) and both domains' dispatch tools (`dispatch_worker`,
`dispatch_stage`) at once -- see `agentcore/prompts/planner.py` for how the
system prompt tells the model which to try first. Whichever inspection tool
succeeds first is recorded as the run's domain (`state.set_domain`), which
the Reporter later reads to decide how to build the final report.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from .. import state
from ..prompts.planner import SYSTEM_PROMPT
from ..providers import ANTHROPIC_MODEL_DEFAULT, OPENAI_MODEL_DEFAULT, make_provider
from ..tools import PLANNER_TOOLS, dispatch as base_dispatch

MAX_ITERATIONS = 40


def make_dispatch(
    run_id: str,
    auto_approve: bool,
    *,
    provider_name: str,
    api_key: str,
    model: str,
    base_url: str | None,
    effort: str,
    emit_fn: Callable[..., None] | None = None,
):
    """Return a dispatch function for the Planner that handles domain routing
    and sub-agent (worker/stage/reporter) tool calls."""

    def _dispatch(run_id_: str, name: str, tool_input: dict[str, Any], auto_approve_: bool) -> dict[str, Any]:
        if name == "dispatch_worker":
            state.set_domain(run_id_, "bio")
            return _call_worker(run_id_, tool_input, auto_approve_)
        if name == "dispatch_stage":
            state.set_domain(run_id_, "gwas")
            return _call_stage(run_id_, tool_input, auto_approve_)
        if name == "generate_report":
            return _call_reporter(run_id_, auto_approve_)
        output = base_dispatch(run_id_, name, tool_input, auto_approve_)
        # Record domain as soon as the model successfully classifies the input,
        # even before it gets as far as dispatch_worker/dispatch_stage -- lets
        # a resumed/interrupted run's Reporter still know which domain it was.
        if name == "inspect_data_source" and not (isinstance(output, dict) and output.get("error")):
            state.set_domain(run_id_, "bio")
        if name == "inspect_gwas_input" and not (isinstance(output, dict) and output.get("error")):
            state.set_domain(run_id_, "gwas")
        return output

    def _call_worker(run_id_: str, tool_input: dict[str, Any], auto_approve_: bool) -> dict[str, Any]:
        branch = tool_input.get("branch")
        sample_id = tool_input.get("sample_id", "unknown")
        input_path = tool_input.get("input_path", "")
        n_cells = tool_input.get("n_cells")
        scenario = tool_input.get("scenario")
        groups = tool_input.get("groups")
        group_column = tool_input.get("group_column")
        comparison = tool_input.get("comparison")
        paired_normal_id = tool_input.get("paired_normal_id")
        paired_normal_path = tool_input.get("paired_normal_path")

        if branch == "wes":
            from ..domains.bio.agents import wes_agent
            summary = wes_agent.run(
                run_id=run_id_,
                sample_id=sample_id,
                input_path=input_path,
                scenario=scenario,
                paired_normal_id=paired_normal_id,
                paired_normal_path=paired_normal_path,
                comparison=comparison,
                provider_name=provider_name,
                api_key=api_key,
                model=model,
                base_url=base_url,
                effort=effort,
                auto_approve=auto_approve_,
                emit_fn=emit_fn,
            )
            return {"branch": "wes", "sample_id": sample_id, "status": "done", "summary": summary}

        if branch == "scrna":
            from ..domains.bio.agents import scrna_agent
            summary = scrna_agent.run(
                run_id=run_id_,
                sample_id=sample_id,
                input_path=input_path,
                n_cells=n_cells,
                scenario=scenario,
                groups=groups,
                group_column=group_column,
                comparison=comparison,
                provider_name=provider_name,
                api_key=api_key,
                model=model,
                base_url=base_url,
                effort=effort,
                auto_approve=auto_approve_,
                emit_fn=emit_fn,
            )
            return {"branch": "scrna", "sample_id": sample_id, "status": "done", "summary": summary}

        return {"error": f"unknown branch '{branch}'; expected 'wes' or 'scrna'"}

    def _call_stage(run_id_: str, tool_input: dict[str, Any], auto_approve_: bool) -> dict[str, Any]:
        stage = tool_input.get("stage")
        context = tool_input.get("context", {})

        if stage == "v2g":
            from ..domains.gwas.agents import v2g_agent
            summary = v2g_agent.run(
                run_id=run_id_, context=context,
                provider_name=provider_name, api_key=api_key, model=model,
                base_url=base_url, effort=effort, auto_approve=auto_approve_,
                emit_fn=emit_fn,
            )
            return {"stage": "v2g", "status": "done", "summary": summary}

        if stage == "mr":
            from ..domains.gwas.agents import mr_agent
            summary = mr_agent.run(
                run_id=run_id_, context=context,
                provider_name=provider_name, api_key=api_key, model=model,
                base_url=base_url, effort=effort, auto_approve=auto_approve_,
                emit_fn=emit_fn,
            )
            return {"stage": "mr", "status": "done", "summary": summary}

        if stage == "drug":
            from ..domains.gwas.agents import drug_agent
            summary = drug_agent.run(
                run_id=run_id_, context=context,
                provider_name=provider_name, api_key=api_key, model=model,
                base_url=base_url, effort=effort, auto_approve=auto_approve_,
                emit_fn=emit_fn,
            )
            return {"stage": "drug", "status": "done", "summary": summary}

        return {"error": f"unknown stage '{stage}'; expected v2g, mr, or drug"}

    def _call_reporter(run_id_: str, auto_approve_: bool) -> dict[str, Any]:
        from . import reporter
        return reporter.run(
            run_id=run_id_,
            provider_name=provider_name, api_key=api_key, model=model,
            base_url=base_url, effort=effort,
            emit_fn=emit_fn, auto_approve=auto_approve_,
        )

    return _dispatch


def run(
    *,
    run_id: str,
    goal: str,
    input_path: str,
    domain_hint: str | None = None,
    provider_name: str = "anthropic",
    api_key: str = "",
    model: str | None = None,
    base_url: str | None = None,
    effort: str = "high",
    auto_approve: bool = True,
    max_iterations: int = MAX_ITERATIONS,
    input_fn: "Callable[[], str] | None" = None,
    emit_fn: Callable[..., None] | None = None,
) -> str:
    _model = model or (ANTHROPIC_MODEL_DEFAULT if provider_name == "anthropic" else OPENAI_MODEL_DEFAULT)

    _dispatch = make_dispatch(
        run_id, auto_approve,
        provider_name=provider_name, api_key=api_key, model=_model,
        base_url=base_url, effort=effort, emit_fn=emit_fn,
    )

    provider = make_provider(
        provider_name, api_key=api_key, model=_model,
        system_prompt=SYSTEM_PROMPT, base_url=base_url, effort=effort, tools=PLANNER_TOOLS,
    )

    resume_summary = state.summarize_state(run_id)
    hint_line = ""
    if domain_hint == "bio":
        hint_line = "\n\nThe caller indicated this is sequencing data (WES/scRNA) -- start with inspect_data_source unless inspection strongly disagrees."
    elif domain_hint == "gwas":
        hint_line = "\n\nThe caller indicated this is a GWAS summary-statistics file -- start with inspect_gwas_input unless inspection strongly disagrees."

    initial = (
        f"Goal: {goal}\n\n"
        f"Primary input path: {input_path}{hint_line}\n\n"
        f"Checkpoint state for run '{run_id}':\n{resume_summary}\n\n"
        "Begin by inspecting the input to determine whether it is sequencing data "
        "(call inspect_data_source) or a GWAS summary-statistics file (call inspect_gwas_input)."
    )
    provider.send_user_text(initial)
    state.append_log(run_id, {"event": "planner_start", "goal": goal, "input_path": input_path})

    final_text = ""
    for _ in range(max_iterations):
        result = provider.step()
        if result.warning:
            print(f"[planner:warning] {result.warning}")
        if result.thinking:
            print(f"\n[planner:thinking] {result.thinking}\n")
        if result.text:
            print(result.text)
            final_text = result.text
        if result.stop_reason != "tool_use":
            if input_fn is not None and result.text:
                try:
                    user_reply = input_fn()
                except (EOFError, KeyboardInterrupt):
                    user_reply = ""
                if user_reply.strip():
                    provider.send_user_text(user_reply)
                    continue
            break
        tool_results = []
        for call in result.tool_calls:
            print(f"[planner:tool_use] {call['name']}({json.dumps(call['input'])})")
            try:
                output = _dispatch(run_id, call["name"], call["input"], auto_approve)
                is_error = bool(isinstance(output, dict) and output.get("error"))
            except Exception as exc:  # noqa: BLE001 - surfaced to the model
                output = {"error": f"{type(exc).__name__}: {exc}"}
                is_error = True
            print(f"[planner:tool_result] {json.dumps(output, default=str)[:400]}")
            tool_results.append({
                "tool_use_id": call["id"],
                "content": json.dumps(output, default=str),
                "is_error": is_error,
            })
        provider.send_tool_results(tool_results)

    state.append_log(run_id, {"event": "planner_end", "final_text": final_text[:500]})
    return final_text
