"""Run with: PYTHONPATH=src python -m pytest tests/test_debug_output.py"""

from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from subprocess import CompletedProcess
from types import SimpleNamespace

import pytest
from pypdf import PdfReader, PdfWriter
from rich.console import Console
from typer.testing import CliRunner
from yaml import safe_dump

from resume import build, cli, llm
from resume.debug import DebugOutput, debug
from resume.models import JobContext, ResumeConfig, ResumeDraft
from resume.render import resolve_resume


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    config = ResumeConfig.model_validate({
        "experiences": {"oci": {
            "title": "Engineer", "company": "Example", "date": "2024",
            "bullet_points": {
                "primary": {"default": "Built an API."},
                "long": {"default": "Added detailed telemetry."},
                "short": {"default": "Added tests."},
            },
        }},
        "projects": {"demo": {
            "name": "Demo", "date": "2025",
            "bullet_points": {"primary": {"default": "Built a tool."}},
        }},
        "skills": ["Python", "SQL"],
        "education": {
            "institution": "Example University", "degree": "BS", "date": "2025",
            "relevant_courses": "Algorithms",
        },
    })
    draft = ResumeDraft.model_validate({
        "section_order": ["Experience", "Projects", "Skills", "Education"],
        "experiences": [{"id": "oci", "bullet_points": [{"id": "primary"}]}],
        "projects": [{"id": "demo", "bullet_points": [{"id": "primary"}]}],
        "skills": [{"name": "Languages", "skills": ["Python", "SQL"]}],
        "include_relevant_courses": True,
    })
    config_path = tmp_path / "resume.yaml"
    config_path.write_text(safe_dump(config.model_dump()), encoding="utf-8")
    draft_path = tmp_path / "saved.json"
    draft_path.write_text(draft.model_dump_json(), encoding="utf-8")
    template_path = tmp_path / "resume.tex.j2"
    template_path.write_text(
        "\\documentclass{article}\n\\begin{document}\n"
        "{{ resume.education.institution | latex_escape }}\n"
        "{% for entry in resume.experiences %}"
        "{% for bullet in entry.bullet_points %}{{ bullet.text }}\n{% endfor %}"
        "{% endfor %}\\end{document}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "load_dotenv", lambda: False)
    monkeypatch.setenv("OPENAI_API_KEY", "secret-key-that-must-not-be-printed")
    return SimpleNamespace(
        config=config, draft=draft, config_path=config_path,
        draft_path=draft_path, template_path=template_path,
        output_dir=tmp_path / "build",
    )


def install_services(monkeypatch, *, pages=(1,), responses=()):
    """Replace only the external API and compiler; run the actual pipeline."""
    page_results = iter(pages)
    model_results = iter(responses)
    requests = []

    def parse(**kwargs):
        requests.append(kwargs)
        value = next(model_results)
        if isinstance(value, Exception):
            raise value
        parsed = None if value is None else kwargs["text_format"].model_validate(value)
        return SimpleNamespace(
            output_parsed=parsed, id="test-response", status="completed",
            usage={"input_tokens": 100, "output_tokens": 30},
            output=[{"type": "refusal", "refusal": "No parsed output"}] if parsed is None else [],
        )

    client = SimpleNamespace(responses=SimpleNamespace(parse=parse))
    monkeypatch.setattr(llm, "OpenAI", lambda **kwargs: client)
    monkeypatch.setattr(build, "which", lambda executable: "/fake/latexmk")

    def compile_or_clean(command, *, cwd, **kwargs):
        if "-c" in command:
            return CompletedProcess(command, 0, "Cleaned auxiliary files", "")
        page_count = next(page_results)
        if page_count is None:
            return CompletedProcess(command, 1, "Compiler stdout [literal]", "Undefined control sequence")
        output_dir = Path(next(item.removeprefix("-outdir=") for item in command if item.startswith("-outdir=")))
        writer = PdfWriter()
        for _ in range(page_count):
            writer.add_blank_page(width=612, height=792)
        writer.write(output_dir / Path(command[-1]).with_suffix(".pdf"))
        return CompletedProcess(command, 0, "Compiler stdout [literal]", "Compiler diagnostic")

    monkeypatch.setattr(build, "run_subprocess", compile_or_clean)
    return requests


def invoke(inputs, *extra, saved=True):
    args = [
        "--jd", "Build [bold]backend[/bold] systems.",
        "--config", str(inputs.config_path),
        "--template", str(inputs.template_path),
        "--output-dir", str(inputs.output_dir),
        "--model", "test-model",
    ]
    if saved:
        args += ["--draft-file", str(inputs.draft_path)]
    return CliRunner().invoke(cli.app, [*args, *extra])


def artifacts(directory):
    return {path.name: path.read_bytes() for path in directory.iterdir()}


@pytest.mark.parametrize("flag", ["--debug", "-D"])
def test_cli_debug_is_optional_and_does_not_change_artifacts(inputs, monkeypatch, flag):
    install_services(monkeypatch)
    quiet = invoke(inputs, "--max-backfill-attempts", "0")
    assert quiet.exit_code == 0, quiet.exception
    assert quiet.output == ""
    expected = artifacts(inputs.output_dir)

    install_services(monkeypatch)
    verbose = invoke(inputs, "--max-backfill-attempts", "0", flag)
    assert verbose.exit_code == 0, verbose.exception
    assert artifacts(inputs.output_dir) == expected
    assert verbose.stdout == ""
    assert "resume.models.ResumeDraft.validate_draft" in verbose.stderr
    assert "resume.render._resolve_bullet" in verbose.stderr
    assert "PDF page count" in verbose.stderr
    assert "Compiler stdout [literal]" in verbose.stderr
    assert "[bold]backend[/bold]" in verbose.stderr
    assert "\x1b[" not in verbose.stderr
    assert "secret-key-that-must-not-be-printed" not in verbose.output
    assert not debug.enabled


def test_fitting_and_backfill_match_quiet_results(inputs, monkeypatch):
    plan = {"additions": [
        {"entry_type": "experience", "entry_id": "oci", "bullet_id": bullet,
         "variant": None, "after_bullet_id": None}
        for bullet in ("long", "short")
    ]}
    responses = [
        inputs.draft.model_dump(),
        {"adjustment": {"action": "remove_relevant_courses"}},
        plan,
    ]
    snapshots = []
    for flags in ((), ("-D",)):
        requests = install_services(monkeypatch, pages=(2, 1, 2, 1), responses=responses)
        result = invoke(inputs, *flags, saved=False)
        assert result.exit_code == 0, result.exception
        assert len(requests) == 3
        snapshots.append(artifacts(inputs.output_dir))
    assert snapshots[0] == snapshots[1]
    final = ResumeDraft.model_validate_json((inputs.output_dir / "draft.json").read_text())
    assert not final.include_relevant_courses
    assert [bullet.id for bullet in final.experiences[0].bullet_points] == ["primary", "short"]
    for message in (
        "OpenAI instructions", "OpenAI prompt", "Parsed response", "Token usage",
        "Request one fitting adjustment", "Reject backfill candidate", "Accept backfill candidate",
        "Restore last accepted file",
    ):
        assert message in result.stderr


@pytest.mark.parametrize("failure", ["compile", "overflow", "render"])
def test_failure_reports_and_debug_state_are_preserved(inputs, monkeypatch, failure):
    install_services(monkeypatch, pages=(None,) if failure == "compile" else (2,))
    if failure == "render":
        inputs.template_path.write_text("{{ missing_value }}", encoding="utf-8")
    result = invoke(inputs, "--max-fit-retries", "0", "--max-backfill-attempts", "0", "-D")
    assert result.exit_code != 0
    assert "FAIL resume.cli.generate" in result.stderr
    assert (inputs.output_dir / "error.json").exists()
    if failure == "compile":
        assert "Undefined control sequence" in result.stderr
        assert (inputs.output_dir / "resume.latexmk.log").exists()
    assert not debug.enabled
    # A second invocation in the same Python process must not inherit -D.
    invalid = CliRunner().invoke(cli.app, [])
    assert "Resume debug" not in invalid.output


@pytest.mark.parametrize("enabled", [False, True])
def test_no_page_limit_skips_pdf_count_and_backfill(inputs, monkeypatch, enabled):
    requests = install_services(monkeypatch, pages=(3,))

    def unexpected_count(*args, **kwargs):
        pytest.fail("Page count must not be read with --no-page-limit")

    monkeypatch.setattr(build, "_get_page_count", unexpected_count)
    result = invoke(inputs, "--no-page-limit", *(["-D"] if enabled else []))
    assert result.exit_code == 0, result.exception
    assert requests == []
    assert len(PdfReader(inputs.output_dir / "resume.pdf").pages) == 3


def test_failed_backfill_restores_last_accepted_artifacts(inputs, monkeypatch):
    install_services(monkeypatch)
    initial = invoke(inputs, "--max-backfill-attempts", "0")
    assert initial.exit_code == 0, initial.exception
    expected = artifacts(inputs.output_dir)
    install_services(monkeypatch, pages=(1, None), responses=[{"additions": [{
        "entry_type": "experience", "entry_id": "oci", "bullet_id": "long",
        "variant": None, "after_bullet_id": None,
    }]}])
    result = invoke(inputs, "-D")
    assert result.exit_code == 0, result.exception
    assert artifacts(inputs.output_dir) == expected
    assert "Skipping backfill candidate that could not compile" in result.stderr


def test_rejected_llm_adjustment_explains_retry(inputs, monkeypatch, capsys):
    requests = install_services(monkeypatch, responses=[
        {"adjustment": {"action": "remove_skill", "category": "Missing", "skill": "Python"}},
        {"adjustment": {"action": "remove_relevant_courses"}},
    ])
    client = llm.OpenAIResumeLLM(model="test-model")
    with debug.session():
        result = client.adjust_draft_once(
            config=inputs.config, draft=inputs.draft,
            resume=resolve_resume(inputs.config, inputs.draft),
            job=JobContext(description="Build software"), actual_pages=2, max_pages=1,
        )
    assert not result.include_relevant_courses
    assert inputs.draft.include_relevant_courses
    assert "Rejected adjustment:" in requests[1]["input"]
    assert "Reject adjustment" in capsys.readouterr().err


@pytest.mark.parametrize("response", [None, RuntimeError("API unavailable")])
def test_llm_failure_keeps_exception_and_closes_debug_session(inputs, monkeypatch, response):
    install_services(monkeypatch, responses=[response])
    result = invoke(inputs, "-D", saved=False)
    assert result.exit_code != 0
    assert "FAIL resume.cli.generate" in result.stderr
    assert "Unparsed response output" in result.stderr if response is None else "API unavailable" in result.stderr
    assert not debug.enabled


def test_terminal_styling_and_spinner_stop_on_failure(monkeypatch):
    monkeypatch.setenv("TERM", "xterm-256color")
    stream = StringIO()
    printer = DebugOutput()
    printer.enabled = True
    printer.console = Console(file=stream, force_terminal=True, width=100)
    # Observe the real Rich status context, including cleanup after an exception.
    status = printer.console.status
    transitions = []

    @contextmanager
    def observed_status(*args, **kwargs):
        with status(*args, **kwargs):
            transitions.append("started")
            try:
                yield
            finally:
                transitions.append("stopped")

    monkeypatch.setattr(printer.console, "status", observed_status)
    with pytest.raises(ValueError, match="broken"):
        with printer.step("External call", spinner=True):
            printer.dump("Literal output", "[bold]not markup[/bold]")
            raise ValueError("broken")
    assert transitions == ["started", "stopped"]
    assert "\x1b[" in stream.getvalue()
    assert "[bold]not markup[/bold]" in stream.getvalue()
    assert "FAIL External call" in stream.getvalue()
    assert printer._depth == 0
