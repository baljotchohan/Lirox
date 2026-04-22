"""End-to-end production vertical slice for code generation workflows."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from lirox.execution.generator import CodeGenerator, GeneratedCode
from lirox.execution.runner import CodeRunner, RunResult
from lirox.learning.manager import LearningManager
from lirox.safety.audit import log_audit_event
from lirox.tools.document_creators import create_docx, create_pdf


@dataclass
class VerticalSliceRequest:
    language: str
    description: str
    provider: str = "auto"
    output_dir: str = ""
    document_format: str = "docx"  # docx | pdf | none
    user_name: str = ""
    run_timeout: int = 15
    train_learning: bool = True


@dataclass
class VerticalSliceResult:
    ok: bool
    code: GeneratedCode
    run: Optional[RunResult] = None
    artifact_path: str = ""
    document_receipt: Dict[str, Any] = field(default_factory=dict)
    learning_stats: Dict[str, Any] = field(default_factory=dict)
    error: str = ""


def execute_vertical_slice(req: VerticalSliceRequest) -> VerticalSliceResult:
    from lirox.config import OUTPUTS_DIR

    out_root = Path(req.output_dir or OUTPUTS_DIR).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    workdir = out_root / f"vertical_slice_{run_id}"
    workdir.mkdir(parents=True, exist_ok=True)

    gen = CodeGenerator(provider=req.provider)
    generated = gen.generate(req.language, req.description)
    if not generated.ok:
        log_audit_event("vertical_slice_generate", req.description, status="error", detail=generated.error)
        return VerticalSliceResult(ok=False, code=generated, error=generated.error or "Generation failed")

    code_path = workdir / (generated.filename or f"generated.{req.language}")
    code_path.write_text(generated.code, encoding="utf-8")
    log_audit_event("vertical_slice_generate", str(code_path), status="ok", detail="Code generated and written")

    run_result: Optional[RunResult] = None
    if generated.language == "python":
        run_result = CodeRunner(timeout=req.run_timeout, workdir=str(workdir)).run(generated.code, language="python")
        log_audit_event(
            "vertical_slice_execute",
            str(code_path),
            status="ok" if run_result.success else "error",
            detail=(run_result.error or run_result.output)[:1200],
        )

    summary_path = workdir / "artifact_summary.txt"
    summary = _build_summary(req, generated, run_result, code_path)
    summary_path.write_text(summary, encoding="utf-8")

    receipt_dict: Dict[str, Any] = {}
    if req.document_format.lower() in {"docx", "pdf"}:
        sections = [{
            "heading": "Request",
            "body": req.description,
            "bullets": [f"Language: {generated.language}", f"File: {code_path.name}"],
        }, {
            "heading": "Execution",
            "body": (run_result.output if run_result and run_result.success else (run_result.error if run_result else "Execution skipped")),
            "bullets": generated.dependencies[:8],
        }]
        doc_title = f"Lirox Vertical Slice — {generated.language.title()}"
        if req.document_format.lower() == "pdf":
            receipt = create_pdf(str(workdir / "artifact_report.pdf"), doc_title, sections, query=req.description, user_name=req.user_name)
        else:
            receipt = create_docx(str(workdir / "artifact_report.docx"), doc_title, sections, query=req.description, user_name=req.user_name)
        receipt_dict = {
            "ok": receipt.ok,
            "verified": receipt.verified,
            "path": receipt.path,
            "error": receipt.error,
            "message": receipt.message,
        }

    learning_stats: Dict[str, Any] = {}
    if req.train_learning:
        try:
            lm = LearningManager(provider=req.provider, use_db=True)
            convo = f"User: {req.description}\nAssistant: {summary[:3000]}"
            learning_stats = lm.train_from_text(convo)
        except Exception:
            learning_stats = {}

    return VerticalSliceResult(
        ok=True,
        code=generated,
        run=run_result,
        artifact_path=str(summary_path),
        document_receipt=receipt_dict,
        learning_stats=learning_stats,
    )


def _build_summary(
    req: VerticalSliceRequest,
    generated: GeneratedCode,
    run_result: Optional[RunResult],
    code_path: Path,
) -> str:
    lines = [
        "LIROX VERTICAL SLICE REPORT",
        f"Description: {req.description}",
        f"Language: {generated.language}",
        f"Generated file: {code_path}",
        f"Dependencies: {', '.join(generated.dependencies) if generated.dependencies else 'none'}",
        "",
    ]
    if run_result is None:
        lines.append("Execution: skipped (non-Python language)")
    else:
        lines.append(f"Execution success: {run_result.success}")
        lines.append(f"Exit code: {run_result.exit_code}")
        lines.append(f"Output: {(run_result.output or '').strip()[:1200]}")
        if run_result.error:
            lines.append(f"Error: {run_result.error[:1200]}")
    return "\n".join(lines).strip() + "\n"

