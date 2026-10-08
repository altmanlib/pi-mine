"""synthesize command: candidates → LLM conclusions."""

from pathlib import Path

import click

from app.models import SynthesisResult
from app.options import json_option, out_dir_option
from app.output import output_json, print_lines
from app.services.llm import DEFAULT_LLM_MODEL, LLM_CACHE_DIRNAME, LlmConfig, LlmError, cached_chat, cpa_chat
from app.services.synthesize import run_synthesis


def _summary_lines(result: SynthesisResult) -> list[str]:
    return [
        f"model: {result.model}",
        f"cluster_backend: {result.cluster_backend}",
        f"candidate_count: {result.candidate_count}",
        f"summary_count: {len(result.summary)}",
        f"conclusion_count: {len(result.conclusions)}",
        f"dropped_count: {result.dropped_count}",
        f"conclusions_md: {result.conclusions_md_path}",
        f"conclusions_json: {result.conclusions_json_path}",
    ]


@click.command("synthesize")
@out_dir_option
@click.option("--model", default=DEFAULT_LLM_MODEL, show_default=True, help="CPA model id")
@json_option
def synthesize_cmd(out_dir: Path, model: str, as_json: bool) -> None:
    """Synthesize candidates into evidence-backed conclusions via CPA (sends candidate patterns)."""
    try:
        config = LlmConfig.from_env(model)
        chat = cached_chat(cpa_chat(config), out_dir / LLM_CACHE_DIRNAME, model)
        result = run_synthesis(out_dir, chat, model)
    except (FileNotFoundError, LlmError) as error:
        raise click.ClickException(str(error)) from error
    if as_json:
        output_json(result.to_dict())
    else:
        print_lines(_summary_lines(result))
