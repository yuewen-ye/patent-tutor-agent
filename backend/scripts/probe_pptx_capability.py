"""Probe configured providers for OpenAI-style direct-file generation prerequisites.

The probe asks each model to use Code Interpreter to create one tiny text file, then reports
whether the response contains an actual tool call or file annotation. API keys are never logged.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import httpx

from backend.app.core.agent_runtime_config import load_agent_runtime_config
from backend.app.core.llm import load_provider_config


def _probe(client: httpx.Client, url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
    try:
        response = client.post(url, headers=headers, json=body)
        try:
            payload: object = response.json()
        except json.JSONDecodeError:
            payload = None
        return {
            "status_code": response.status_code,
            "response": payload if response.status_code == 200 else response.text[:500],
        }
    except httpx.HTTPError as exc:
        return {"transport_error": f"{type(exc).__name__}: {exc}"}


def _tool_evidence(payload: object) -> dict[str, bool]:
    encoded = json.dumps(payload, ensure_ascii=False).lower()
    return {
        "tool_call": "code_interpreter_call" in encoded or "code_interpreter" in encoded,
        "file_reference": "file_id" in encoded or "container_file_citation" in encoded,
    }


def main() -> None:
    config = load_agent_runtime_config()
    report: list[dict[str, Any]] = []
    with httpx.Client(timeout=90.0) as client:
        for provider_name in sorted(config.providers):
            provider = config.providers[provider_name]
            try:
                resolved = load_provider_config(provider_name, model_name=provider.model_name)
            except Exception as exc:  # noqa: BLE001 - diagnostics must continue per provider
                report.append({"provider": provider_name, "configuration_error": str(exc)})
                continue
            url = resolved.base_url.rstrip("/") + "/responses"
            headers = {"Authorization": f"Bearer {resolved.api_key}", "Content-Type": "application/json"}
            basic = _probe(
                client, url, headers, {"model": resolved.model, "input": "Reply exactly: ok"}
            )
            tool = _probe(
                client,
                url,
                headers,
                {
                    "model": resolved.model,
                    "input": (
                        "Use the code_interpreter tool now. Create /mnt/data/ppt_probe.txt containing "
                        "exactly pptx-capable, then attach the created file in your final response."
                    ),
                    "tools": [{"type": "code_interpreter"}],
                },
            )
            report.append(
                {
                    "provider": provider_name,
                    "model": resolved.model,
                    "base_url": resolved.base_url,
                    "responses_status": basic.get("status_code"),
                    "code_interpreter_status": tool.get("status_code"),
                    "code_interpreter_evidence": _tool_evidence(tool.get("response")),
                    "error_preview": tool.get("response") if tool.get("status_code") != 200 else None,
                }
            )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
