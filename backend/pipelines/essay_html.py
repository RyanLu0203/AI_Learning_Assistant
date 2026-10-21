from __future__ import annotations

import json
from typing import Any, Callable

from backend.artifacts.filesystem import ArtifactRun
from backend.pipelines.authorship import add_author_credit
from backend.pipelines.common import (
    PipelineError,
    PipelineResult,
    extract_fenced_or_raw,
    format_citations,
    format_log,
)
from backend.pipelines.html_to_pdf import (
    A4_PAGE,
    ConvertError,
    HtmlToPdfConverter,
)
from backend.providers.base import (
    ModelProviderError,
    TextGenerationProvider,
    TextGenerationRequest,
)
from backend.timing import RunTimingRecorder, measure_stage


BA3073_REPORT_INSTRUCTIONS = """[BA3073 Deployment Report Requirements]
Write the BA3073 individual assignment, From AI Agent to Cloud Service, using
only the deployment evidence supplied in the task and prepared context.

Structure the report as: title and student identity (only if supplied), abstract,
system architecture, Task 1 local Docker deployment, report-prompt improvements,
Task 2 Alibaba Cloud ACR and ECS deployment, Task 3 domain/DNS/Nginx/HTTPS and
reverse-proxy access control, verification results, security and cost analysis,
limitations and improvements, conclusion, and references.

Explain the role of FastAPI, the browser UI, SQLite metadata, the mounted data/
and workspace/ directories, the OpenAI-compatible model API, and Playwright
HTML-to-PDF conversion. Describe the actual configured provider, model, CPU
architecture, image tag/digest, commands, URLs, and observed test results only
when supplied. Distinguish the ARM Mac build from an amd64 ECS image if relevant.
Explain the ACR push/pull path and why rebuilding or replacing a container must
preserve the bind-mounted database, encryption master key, and generated files.

Discuss Task 1's local-ui-check.txt and Task 2's ecs-docker-check.txt. Include
an evidence table linking each requirement to its supplied evidence ID, capture
time, observed result, and status. A command being recommended is not evidence
that it ran. Never invent successful checks, screenshots, IP addresses, domains,
student details, cloud resources, measurements, prices, or references. Mark
missing evidence as NOT VERIFIED and describe the remaining action explicitly.
Label example commands and proposed improvements separately from completed work.

Include the supplied browser screenshots for local and ECS-IP access, plus the
HTTPS domain URL and the successful reverse-proxy access-control screenshot.
Preserve the visible address bar. Embed an image only when its actual image data
or supported local image reference was supplied. Otherwise use a clearly labelled
missing-evidence note; never create a simulated screenshot or fake browser chrome.
Use figure captions with evidence IDs so genuine screenshots can be inserted.

Explain that Task 2 temporarily permits port 14242 only from the student's public
IP. For Task 3, explain DNS A resolution, Nginx forwarding to 127.0.0.1:14242,
ports 80/443, certificate issuance/renewal, and closing public port 14242.
The extra reverse-proxy authentication must be separate from the application's
BNBU login. Report whether unauthenticated and authenticated access were tested.
Never print API keys, passwords, bearer tokens, private keys, or encryption keys.
Explain secret storage, backups, API usage costs, ECS/storage/bandwidth/domain
cost categories, and cleanup of chargeable resources without inventing amounts.

Explain how the revised essay_html.py instructions improve structure, factual
grounding, evidence coverage, and clarity over the original generic essay prompt.
Use the requested report language and precise, readable technical prose. Aim for
10-14 A4 pages including figures and references, with an absolute maximum of
20 pages. Use compact tables, readable 10.5-11pt text, inline CSS and sensible
page breaks; avoid clipped commands, oversized figures and near-empty pages.
Do not claim a final page count until the rendered PDF has been checked.
"""


def run_essay_html_pipeline(
    *,
    artifact_run: ArtifactRun,
    model_profile: dict[str, Any],
    model_provider: TextGenerationProvider,
    pdf_converter: HtmlToPdfConverter,
    task_text: str,
    context_bundle: str,
    output_preference: str | None,
    options: dict[str, Any] | None,
    search: dict[str, Any],
    max_output_tokens: int,
    emit_event: Callable[[str, str], None] | None = None,
    timing: RunTimingRecorder | None = None,
) -> PipelineResult:
    log_lines = [
        "Pipeline: essay_html",
        f"Output preference: {output_preference or 'pdf'}",
        "Stage: generate_source",
    ]
    system_prompt, user_prompt = build_essay_html_prompt(
        task_text=task_text,
        context_bundle=context_bundle,
        options=options or {},
        search=search,
    )
    if emit_event:
        emit_event("generate_source", "Generating essay HTML source")

    try:
        with measure_stage(timing, "provider_generation"):
            raw_output = model_provider.generate_text(
                TextGenerationRequest(
                    profile=model_profile,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_output_tokens=max_output_tokens,
                    temperature=0.2,
                )
            )
    except ModelProviderError as exc:
        raise PipelineError(
            exc.code,
            exc.message,
            stage="generate_source",
            log_lines=log_lines,
        ) from exc
    except Exception as exc:
        raise PipelineError(
            "provider_unavailable",
            "The model provider request failed.",
            stage="generate_source",
            log_lines=log_lines,
        ) from exc

    source = extract_fenced_or_raw(raw_output, accepted_languages={"html", "htm"})
    source = add_author_credit(source.strip()) + "\n"
    html_path = artifact_run.write_output(
        "main.html",
        source,
        kind="source",
        media_type="text/html",
    )
    log_lines.extend(["Output: output/main.html", "Stage: convert_pdf"])
    if emit_event:
        emit_event("convert_pdf", "Converting essay HTML to PDF")

    pdf_path = artifact_run.run_dir / "output" / "main.pdf"
    try:
        with measure_stage(timing, "convert_pdf"):
            convert_result = pdf_converter.convert(
                html_path=html_path,
                pdf_path=pdf_path,
                page_config=A4_PAGE,
            )
    except ConvertError as exc:
        artifact_run.write_log("convert.log", exc.log_text)
        raise PipelineError(
            "convert_failed",
            exc.message,
            stage="convert_pdf",
            log_lines=log_lines,
        ) from exc
    except Exception as exc:
        artifact_run.write_log(
            "convert.log",
            "HTML-to-PDF converter raised an unexpected error.\n",
        )
        raise PipelineError(
            "convert_failed",
            "HTML-to-PDF conversion failed.",
            stage="convert_pdf",
            log_lines=log_lines,
        ) from exc

    artifact_run.write_log("convert.log", convert_result.log_text)
    artifact_run.write_output(
        "main.pdf",
        convert_result.pdf_path.read_bytes(),
        kind="pdf",
        media_type="application/pdf",
    )
    log_lines.extend(["Convert: pdf_ok", "Output: output/main.pdf"])
    return PipelineResult(log_text=format_log(log_lines))


def build_essay_html_prompt(
    *,
    task_text: str,
    context_bundle: str,
    options: dict[str, Any],
    search: dict[str, Any],
) -> tuple[str, str]:
    system_prompt = (
        "You are an expert teaching assistant writing complete academic essay and "
        "report deliverables as self-contained HTML documents. Return only the "
        "requested HTML source, with no surrounding explanation."
    )
    task_lower = task_text.casefold()
    if "ba3073" in task_lower or "from ai agent to cloud service" in task_lower:
        system_prompt += "\n\n" + BA3073_REPORT_INSTRUCTIONS
    output_instruction = (
        "Return one complete self-contained HTML document. It must start with "
        "<!doctype html> and include <html>, <head>, and <body>. Include all CSS "
        "inside a <style> element: use a readable serif academic print layout, "
        "clear heading hierarchy, careful paragraph spacing, and CSS "
        "@page { size: A4; margin: 20mm; }. Do not use external stylesheet links, "
        "remote images, or remote HTTP(S) assets. If mathematical notation is "
        "needed, include inline KaTeX-compatible markup and any needed minimal "
        "KaTeX styling inline in the document; do not fetch KaTeX from a CDN at "
        "render time. Use inline SVG or CSS for diagrams. Cite any provided web "
        "sources in a References section using ordinary HTML. Do not wrap the "
        "answer in Markdown fences."
    )
    user_prompt = "\n\n".join(
        [
            "[Assignment Task]\n" + task_text.strip(),
            "[Prepared Context]\n" + context_bundle.strip(),
            "[Search Citations]\n" + format_citations(search),
            "[Options]\n" + json.dumps(options, sort_keys=True),
            "[Output Contract]\n" + output_instruction,
        ]
    )
    return system_prompt, user_prompt
