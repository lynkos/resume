from __future__ import annotations
from pathlib import Path
from typing import Annotated
from typer import Typer, BadParameter, Option
from dotenv import load_dotenv
from .build import build_resume
from .config import load_job_description, load_resume_config
from .debug import debug as debug_output
from .llm import OpenAIResumeLLM
from .models import JobContext, ResumeDraft

app = Typer(no_args_is_help=True, help="Generate a JD-tailored LaTeX/PDF resume.", pretty_exceptions_show_locals=False)


@app.command()
def generate(
    jd_file: Annotated[Path | None, Option("--jd-file", help="Path to a text file containing the job description.")] = None,
    jd: Annotated[str | None, Option("--jd", help="Literal job-description text.")] = None,
    title: Annotated[str | None, Option("--title", help="Optional job title.")] = None,
    company: Annotated[str | None, Option("--company", help="Optional company name.")] = None,
    config_path: Annotated[Path, Option("--config", help="Resume YAML source of truth.")] = Path("resume.yaml"),
    template_path: Annotated[Path, Option("--template", help="Jinja LaTeX template.")] = Path("resume.tex.j2"),
    output_dir: Annotated[Path, Option("--output-dir", help="Directory for generated TeX/PDF/debug files.")] = Path("Resume/build"),
    output_name: Annotated[str, Option("--output-name", help="Base filename for generated TeX/PDF.")] = "resume",
    max_pages: Annotated[int, Option("--max-pages", min=1, help="Maximum allowed PDF page count.")] = 1,
    no_page_limit: Annotated[bool, Option("--no-page-limit", help="Disable the PDF page-count requirement.")] = False,
    max_fit_retries: Annotated[int, Option("--max-fit-retries", min=0, help="Maximum number of one-change fitting retries.")] = 8,
    max_backfill_attempts: Annotated[int, Option("--max-backfill-attempts", min=0, help="Maximum additions tested after fitting; 0 disables backfilling.")] = 6,
    draft_file: Annotated[Path | None, Option("--draft-file", exists=True, dir_okay=False, help="Start from a saved draft instead of generating a new selection.")] = None,
    model: Annotated[str | None, Option("--model", help="OpenAI model; otherwise uses OPENAI_MODEL from .env.")] = None,
    debug: Annotated[bool, Option("--debug", "-D", help="Print detailed execution traces, prompts, responses, and compiler output to stderr.")] = False,
) -> None:
    with debug_output.session(debug), debug_output.step("resume.cli.generate"):
        with debug_output.step("Load .env"):
            load_dotenv()

        debug_output.print("Validate job-description arguments", jd_file=jd_file, literal_jd=jd is not None)
        if (jd_file is None) == (jd is None):
            raise BadParameter("Provide exactly one of --jd-file or --jd")

        job_description = load_job_description(jd_file if jd_file is not None else jd or "")
        with debug_output.step("Validate JobContext"):
            job = JobContext(description=job_description, title=title, company=company)
        #debug_output.dump("Job context", job)
        config = load_resume_config(config_path)
        llm = OpenAIResumeLLM(model=model)

        page_limit = None if no_page_limit else max_pages
        debug_output.print(
            "Build options", template=template_path, output_dir=output_dir,
            output_name=output_name, max_pages=page_limit,
            max_fit_retries=max_fit_retries, max_backfill_attempts=max_backfill_attempts,
        )
        if draft_file is not None:
            debug_output.print("Read saved draft", path=draft_file)
            with debug_output.step("Read and validate ResumeDraft"):
                draft = ResumeDraft.model_validate_json(draft_file.read_text(encoding="utf-8"))
        else:
            debug_output.print("Generate initial draft")
            draft = llm.create_draft(config, job, max_pages=page_limit)
        debug_output.dump("Initial draft", draft)

        debug_output.print("Create output directory", path=output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        draft_path = output_dir / "draft.json"
        debug_output.print("Write initial draft", path=draft_path)
        draft_path.write_text(draft.model_dump_json(indent=2), encoding="utf-8")

        build_resume(
            config=config,
            draft=draft,
            job=job,
            llm=llm,
            template_path=template_path,
            output_dir=output_dir,
            output_name=output_name,
            max_pages=page_limit,
            max_fit_retries=max_fit_retries,
            max_backfill_attempts=max_backfill_attempts,
        )
        debug_output.print("Resume ready", pdf=output_dir / f"{output_name}.pdf")


if __name__ == "__main__":
    app()