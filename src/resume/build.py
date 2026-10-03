from __future__ import annotations
from json import dumps
from shutil import which
from subprocess import run as run_subprocess
from pathlib import Path
from os import environ
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from .error import ResumeBuildError, ResumeCompileError, ResumeOverflowError, ResumeLLMError
from .llm import OpenAIResumeLLM, apply_bullet_addition
from .render import render_resume
from .models import JobContext, Resume, ResumeConfig, ResumeDraft

def _clean_latex_artifacts(tex_path: Path) -> None:
    run_subprocess(
        [
            "latexmk",
            "-c",
            tex_path.name,
        ],
        cwd=tex_path.parent,
        check=False,
        capture_output=True,
        text=True,
    )

    latexmk_log = tex_path.parent / f"{tex_path.stem}.latexmk.log"
    latexmk_log.unlink(missing_ok=True)


def _finish_build(tex_path: Path) -> None:
    _clean_latex_artifacts(tex_path)
    (tex_path.parent / "error.json").unlink(missing_ok=True)


def compile_resume(*, tex_path: Path, output_dir: Path) -> Path:
    if not which("latexmk"):
        raise ResumeCompileError("latexmk is not installed or not available on PATH")

    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        "latexmk",
        "-pdf",
        "-lualatex", # Get contact info from .env
        "-interaction=nonstopmode",
        "-file-line-error",
        "-halt-on-error",
        f"-outdir={output_dir.resolve()}",
        tex_path.name,
    ]

    result = run_subprocess(
        command,
        cwd=tex_path.parent,
        capture_output=True,
        text=True,
        check=False,
        env=environ.copy(),
    )

    latexmk_log = output_dir / f"{tex_path.stem}.latexmk.log"
    latexmk_log.write_text(f"COMMAND: {' '.join(command)}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}\n", encoding="utf-8")

    pdf_path = output_dir / f"{tex_path.stem}.pdf"
    if result.returncode != 0 or not pdf_path.exists():
        raise ResumeCompileError(f"LaTeX compilation failed. Generated TeX: {tex_path}. Log: {latexmk_log}")

    return pdf_path


def _get_page_count(pdf_path: Path) -> int:
    try:
        return len(PdfReader(pdf_path).pages) # str(pdf_path)
    except PdfReadError as exc:
        raise ResumeCompileError(f"Generated PDF could not be read: {pdf_path}. Check if another LaTeX process is writing to the same output.") from exc


def build_resume(
    *,
    config: ResumeConfig,
    draft: ResumeDraft,
    job: JobContext,
    llm: OpenAIResumeLLM,
    template_path: Path,
    output_dir: Path,
    output_name: str = "resume",
    max_pages: int | None = 1,
    max_fit_retries: int = 8,
    max_backfill_attempts: int = 6,
) -> None:
    if max_pages is not None and max_pages < 1:
        raise ValueError("max_pages must be >= 1 or None")
    if max_fit_retries < 0:
        raise ValueError("max_fit_retries must be >= 0")
    if max_backfill_attempts < 0:
        raise ValueError("max_backfill_attempts must be >= 0")

    working_draft = draft.model_copy(deep=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Reserve most attempts for content removal if wording edits do not fit.
    wording_attempts = min(2, max_fit_retries // 2)

    for retry in range(max_fit_retries + 1):
        draft_path = output_dir / "draft.json"
        draft_path.write_text(working_draft.model_dump_json(indent=2), encoding="utf-8")

        try:
            tex_path, resume = render_resume(
                config=config,
                draft=working_draft,
                template_path=template_path,
                output_dir=output_dir,
                output_name=output_name,
            )
        except Exception as exc:
            debug_path = output_dir / f"{output_name}.debug.tex"
            payload = {
                "type": "render_or_resolve",
                "error": f"{type(exc).__name__}: {exc}",
                "debug_tex_path": str(debug_path),
                "fit_retry": retry
            }
            
            (output_dir / "error.json").write_text(dumps(payload, indent=2), encoding="utf-8")
            raise ResumeBuildError(f"Resume resolution/rendering failed. Debug TeX: {debug_path}") from exc

        try:
            pdf_path = compile_resume(
                tex_path=tex_path,
                output_dir=output_dir,
            )
            actual_pages = _get_page_count(pdf_path) if max_pages is not None else None
        except ResumeCompileError as exc:
            payload = {
                "type": "compile",
                "error": str(exc),
                "tex_path": str(tex_path),
                "fit_retry": retry
            }
            
            (output_dir / "error.json").write_text(dumps(payload, indent=2), encoding="utf-8")
            raise ResumeCompileError(f"Resume compilation failed. Debug TeX: {str(tex_path)}") from exc

        if max_pages is None: return _finish_build(tex_path)

        assert actual_pages is not None
        if actual_pages <= max_pages:
            if max_backfill_attempts:
                _backfill_resume(
                    config=config,
                    draft=working_draft,
                    resume=resume,
                    job=job,
                    llm=llm,
                    template_path=template_path,
                    output_dir=output_dir,
                    output_name=output_name,
                    tex_path=tex_path,
                    pdf_path=pdf_path,
                    max_pages=max_pages,
                    max_attempts=max_backfill_attempts,
                )
            return _finish_build(tex_path)

        if retry == max_fit_retries:
            payload = {
                        "type": "overflow",
                        "max_pages": max_pages,
                        "actual_pages": actual_pages,
                        "fit_retries": max_fit_retries,
                        "tex_path": str(tex_path),
                        "pdf_path": str(pdf_path)
            }
            
            (output_dir / "error.json").write_text(dumps(payload, indent=2), encoding="utf-8")            
            raise ResumeOverflowError(f"Could not fit resume within {max_pages} page(s) after {max_fit_retries} corrective retries")

        working_draft = llm.adjust_draft_once(
            config=config,
            draft=working_draft,
            resume=resume,
            job=job,
            actual_pages=actual_pages,
            max_pages=max_pages,
            allow_rewrite=retry < wording_attempts,
        )

    raise AssertionError("Unreachable")


def _backfill_resume(
    *,
    config: ResumeConfig,
    draft: ResumeDraft,
    resume: Resume,
    job: JobContext,
    llm: OpenAIResumeLLM,
    template_path: Path,
    output_dir: Path,
    output_name: str,
    tex_path: Path,
    pdf_path: Path,
    max_pages: int,
    max_attempts: int,
) -> None:
    try:
        additions = llm.suggest_additions(
            config=config,
            draft=draft,
            resume=resume,
            job=job,
            max_candidates=max_attempts
        )
    except ResumeLLMError as exc:
        print(f"Keeping the fitted resume; backfill skipped: {exc}")
        return

    if not additions: return
    draft_path = output_dir / "draft.json"
    # Trials reuse the output paths. Always restore all three files together.
    kept = {path: path.read_bytes() for path in (tex_path, pdf_path, draft_path)}
    working = draft
    try:
        for addition in additions[:max_attempts]:
            try:
                trial = apply_bullet_addition(config, working, addition)
            except ResumeLLMError as exc:
                print(f"Skipping invalid backfill candidate: {exc}")
                continue
            try:
                trial_tex, _ = render_resume(
                    config=config, draft=trial, template_path=template_path,
                    output_dir=output_dir, output_name=output_name,
                )
                trial_pdf = compile_resume(tex_path=trial_tex, output_dir=output_dir)
                pages = _get_page_count(trial_pdf)
            except ResumeCompileError as exc:
                print(f"Skipping backfill candidate that could not compile: {exc}")
                continue
            if pages <= max_pages:
                draft_path.write_text(trial.model_dump_json(indent=2), encoding="utf-8")
                kept = {path: path.read_bytes() for path in kept}
                working = trial
    finally:
        for path, content in kept.items():
            path.write_bytes(content)
