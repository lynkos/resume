from __future__ import annotations
from json import dumps
from shutil import which
from shlex import join
from subprocess import run as run_subprocess
from pathlib import Path
from os import environ
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from .debug import debug
from .error import ResumeBuildError, ResumeCompileError, ResumeOverflowError, ResumeLLMError
from .llm import OpenAIResumeLLM, apply_bullet_addition
from .render import render_resume
from .models import JobContext, Resume, ResumeConfig, ResumeDraft

@debug.trace
def _clean_latex_artifacts(tex_path: Path) -> None:
    command = ["latexmk", "-c", tex_path.name]
    debug.print("Run cleanup command", command=join(command), cwd=tex_path.parent)
    with debug.step("latexmk cleanup", spinner=True):
        result = run_subprocess(
            command,
            cwd=tex_path.parent,
            check=False,
            capture_output=True,
            text=True,
        )
    debug.print("Cleanup finished", returncode=result.returncode)
    #debug.dump("Cleanup stdout", result.stdout)
    #debug.dump("Cleanup stderr", result.stderr)

    latexmk_log = tex_path.parent / f"{tex_path.stem}.latexmk.log"
    debug.print("Remove temporary compiler log", path=latexmk_log)
    latexmk_log.unlink(missing_ok=True)


@debug.trace
def _finish_build(tex_path: Path) -> None:
    _clean_latex_artifacts(tex_path)
    debug.print("Remove stale error report", path=tex_path.parent / "error.json")
    (tex_path.parent / "error.json").unlink(missing_ok=True)


@debug.trace
def compile_resume(*, tex_path: Path, output_dir: Path) -> Path:
    executable = which("latexmk")
    debug.print("Locate latexmk", executable=executable)
    if not executable:
        raise ResumeCompileError("latexmk is not installed or not available on PATH")

    debug.print("Create compiler output directory", path=output_dir)
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

    debug.print("Run compiler command", command=join(command), cwd=tex_path.parent)
    with debug.step("latexmk compilation", spinner=True):
        result = run_subprocess(
            command,
            cwd=tex_path.parent,
            capture_output=True,
            text=True,
            check=False,
            env=environ.copy(),
        )
    debug.print("Compiler finished", returncode=result.returncode)
    #debug.dump("Compiler stdout", result.stdout)
    #debug.dump("Compiler stderr", result.stderr)

    latexmk_log = output_dir / f"{tex_path.stem}.latexmk.log"
    debug.print("Write compiler diagnostic file", path=latexmk_log)
    latexmk_log.write_text(f"COMMAND: {' '.join(command)}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}\n", encoding="utf-8")

    pdf_path = output_dir / f"{tex_path.stem}.pdf"
    debug.print("Check generated PDF", path=pdf_path)
    if result.returncode != 0 or not pdf_path.exists():
        raise ResumeCompileError(f"LaTeX compilation failed. Generated TeX: {tex_path}. Log: {latexmk_log}")

    return pdf_path


@debug.trace
def _get_page_count(pdf_path: Path) -> int:
    debug.print("Read PDF page count", path=pdf_path)
    try:
        pages = len(PdfReader(pdf_path).pages)
        debug.print("PDF page count", pages=pages)
        return pages
    except PdfReadError as exc:
        raise ResumeCompileError(f"Generated PDF could not be read: {pdf_path}. Check if another LaTeX process is writing to the same output.") from exc


@debug.trace
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
    debug.print("Validate build limits", max_pages=max_pages, max_fit_retries=max_fit_retries, max_backfill_attempts=max_backfill_attempts)
    if max_pages is not None and max_pages < 1:
        raise ValueError("max_pages must be >= 1 or None")
    if max_fit_retries < 0:
        raise ValueError("max_fit_retries must be >= 0")
    if max_backfill_attempts < 0:
        raise ValueError("max_backfill_attempts must be >= 0")

    debug.print("Copy draft for fitting")
    working_draft = draft.model_copy(deep=True)
    debug.print("Create build directory", path=output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Reserve most attempts for content removal if wording edits do not fit.
    wording_attempts = min(2, max_fit_retries // 2)
    debug.print("Allocate fitting retries", wording_attempts=wording_attempts, removal_attempts=max_fit_retries - wording_attempts)

    for retry in range(max_fit_retries + 1):
        debug.print("Fit pass", attempt=retry + 1, maximum=max_fit_retries + 1, corrective_retries_used=retry)
        draft_path = output_dir / "draft.json"
        debug.print("Write current draft", path=draft_path)
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
            
            debug.dump("Rendering failure", payload)
            debug.print("Write error report", path=output_dir / "error.json")
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
            
            debug.dump("Compilation failure", payload)
            debug.print("Write error report", path=output_dir / "error.json")
            (output_dir / "error.json").write_text(dumps(payload, indent=2), encoding="utf-8")
            raise ResumeCompileError(f"Resume compilation failed. Debug TeX: {str(tex_path)}") from exc

        if max_pages is None:
            debug.print("Page limit disabled; skip fitting and backfill")
            return _finish_build(tex_path)

        assert actual_pages is not None
        debug.print("Check page limit", actual_pages=actual_pages, max_pages=max_pages, fits=actual_pages <= max_pages)
        if actual_pages <= max_pages:
            if max_backfill_attempts:
                debug.print("Resume fits; start backfill", max_attempts=max_backfill_attempts)
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
            else:
                debug.print("Backfill disabled")
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
            
            debug.dump("Fitting retries exhausted", payload)
            debug.print("Write error report", path=output_dir / "error.json")
            (output_dir / "error.json").write_text(dumps(payload, indent=2), encoding="utf-8")
            raise ResumeOverflowError(f"Could not fit resume within {max_pages} page(s) after {max_fit_retries} corrective retries")

        debug.print("Request one fitting adjustment", retry=retry + 1, allow_rewrite=retry < wording_attempts)
        working_draft = llm.adjust_draft_once(
            config=config,
            draft=working_draft,
            resume=resume,
            job=job,
            actual_pages=actual_pages,
            max_pages=max_pages,
            allow_rewrite=retry < wording_attempts,
        )
        #debug.dump("Adjusted draft", working_draft)

    raise AssertionError("Unreachable")


@debug.trace
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
        debug.warning(f"Keeping the fitted resume; backfill skipped: {exc}")
        return

    debug.print("Backfill plan received", candidates=len(additions), max_attempts=max_attempts)
    if not additions:
        debug.print("No backfill candidates; keep fitted resume")
        return
    draft_path = output_dir / "draft.json"
    # Trials reuse the output paths. Always restore all three files together.
    debug.print("Snapshot fitted TeX, PDF, and draft", paths=(tex_path, pdf_path, draft_path))
    kept = {path: path.read_bytes() for path in (tex_path, pdf_path, draft_path)}
    working = draft
    try:
        for attempt, addition in enumerate(additions[:max_attempts], start=1):
            debug.print("Backfill trial", attempt=attempt, maximum=min(len(additions), max_attempts))
            debug.dump("Backfill candidate", addition)
            try:
                trial = apply_bullet_addition(config, working, addition)
            except ResumeLLMError as exc:
                debug.warning(f"Skipping invalid backfill candidate: {exc}")
                continue
            try:
                trial_tex, _ = render_resume(
                    config=config, draft=trial, template_path=template_path,
                    output_dir=output_dir, output_name=output_name,
                )
                trial_pdf = compile_resume(tex_path=trial_tex, output_dir=output_dir)
                pages = _get_page_count(trial_pdf)
            except ResumeCompileError as exc:
                debug.warning(f"Skipping backfill candidate that could not compile: {exc}")
                continue
            if pages <= max_pages:
                debug.print("Accept backfill candidate", pages=pages, max_pages=max_pages)
                debug.print("Write accepted draft", path=draft_path)
                draft_path.write_text(trial.model_dump_json(indent=2), encoding="utf-8")
                debug.print("Snapshot accepted TeX, PDF, and draft")
                kept = {path: path.read_bytes() for path in kept}
                working = trial
            else:
                debug.print("Reject backfill candidate: page limit exceeded", pages=pages, max_pages=max_pages)
    finally:
        for path, content in kept.items():
            debug.print("Restore last accepted file", path=path, bytes=len(content))
            path.write_bytes(content)
