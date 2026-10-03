from json import loads
from pathlib import Path
from types import SimpleNamespace

import pytest
from pypdf import PdfReader, PdfWriter

from resume import build
from resume.error import ResumeCompileError, ResumeLLMError
from resume.llm import OpenAIResumeLLM, _BackfillPlan, _BulletAddition, apply_bullet_addition
from resume.models import JobContext, ResumeConfig, ResumeDraft
from resume.prompts import build_backfill_prompt
from resume.render import resolve_resume


@pytest.fixture
def config():
    return ResumeConfig.model_validate({
        "experiences": {"work": {
            "title": "Engineer", "company": "Example", "date": "2026",
            "bullet_points": {
                "selected": {"default": "Built a service."},
                "small": {"default": "Added tests.", "variants": {"compact": "Tested it."}},
                "large": {"default": "More detailed work."},
                "bad": {"default": "Invalid LaTeX fixture."},
            },
        }},
        "projects": {}, "skills": ["Python"],
        "education": {"institution": "Example University", "degree": "BS", "date": "2025"},
    })


@pytest.fixture
def draft():
    return ResumeDraft.model_validate({
        "section_order": ["Education", "Experience", "Projects", "Skills"],
        "experiences": [{"id": "work", "bullet_points": [{"id": "selected"}]}],
        "projects": [], "skills": [{"name": "Languages", "skills": ["Python"]}],
    })


def addition(bullet_id, **overrides):
    return _BulletAddition(
        entry_type="experience", entry_id="work", bullet_id=bullet_id,
        **{"variant": None, "after_bullet_id": None, **overrides},
    )


def test_addition_uses_configured_text_and_does_not_mutate_input(config, draft):
    before = draft.model_dump()
    result = apply_bullet_addition(config, draft, addition("small", variant="compact", after_bullet_id="selected"))
    assert [b.id for b in result.experiences[0].bullet_points] == ["selected", "small"]
    assert resolve_resume(config, result).experiences[0].bullet_points[-1].text == "Tested it."
    assert draft.model_dump() == before


@pytest.mark.parametrize("candidate", [
    addition("missing"), addition("selected"), addition("small", variant="missing"),
    addition("small", after_bullet_id="missing"),
    _BulletAddition(entry_type="project", entry_id="unselected", bullet_id="small", variant=None, after_bullet_id=None),
])
def test_invalid_additions_are_rejected(config, draft, candidate):
    with pytest.raises(ResumeLLMError):
        apply_bullet_addition(config, draft, candidate)


def test_default_alias_and_explicit_default_variant(config, draft):
    result = apply_bullet_addition(config, draft, addition("small", variant="default"))
    assert result.experiences[0].bullet_points[-1].variant is None
    config.experiences["work"].bullet_points["small"].variants["default"] = "Named default."
    result = apply_bullet_addition(config, draft, addition("small", variant="default"))
    assert resolve_resume(config, result).experiences[0].bullet_points[-1].text == "Named default."


def test_prompt_contains_only_omitted_candidate_ids(config, draft):
    prompt = build_backfill_prompt(
        config=config, draft=draft, resume=resolve_resume(config, draft),
        job=JobContext(description="Python engineering"), max_candidates=3,
    )
    assert prompt is not None
    candidates = loads(prompt.split("Available omitted bullets (authoritative):\n")[1])
    assert set(candidates["experience"]["work"]) == {"small", "large", "bad"}


def test_no_available_bullets_does_not_call_model(config, draft):
    config.experiences["work"].bullet_points = {"selected": config.experiences["work"].bullet_points["selected"]}
    def unexpected_request(**kwargs):
        pytest.fail("No request should be made without candidates")
    llm = OpenAIResumeLLM(model="test-model", client=SimpleNamespace(responses=SimpleNamespace(parse=unexpected_request))) # type: ignore
    assert llm.suggest_additions(config=config, draft=draft, resume=resolve_resume(config, draft),
                                job=JobContext(description="Python"), max_candidates=6) == []


def test_plan_is_bounded_and_uses_structured_format(config, draft):
    calls = []
    def parse(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(output_parsed=_BackfillPlan(additions=[addition("small"), addition("large")]))
    llm = OpenAIResumeLLM(model="test-model", client=SimpleNamespace(responses=SimpleNamespace(parse=parse))) # type: ignore
    plan = llm.suggest_additions(config=config, draft=draft, resume=resolve_resume(config, draft),
                                job=JobContext(description="Python"), max_candidates=1)
    assert len(calls) == 1
    assert calls[0]["text_format"] is _BackfillPlan
    assert [item.bullet_id for item in plan] == ["small"]


@pytest.fixture
def trial_build(config, draft, tmp_path, monkeypatch):
    compiled = []

    def render(*, draft, output_dir, output_name, **kwargs):
        tex = output_dir / f"{output_name}.tex"
        tex.write_text(draft.model_dump_json())
        return tex, resolve_resume(config, draft)

    def compile(*, tex_path, output_dir):
        state = ResumeDraft.model_validate_json(tex_path.read_text())
        ids = [b.id for b in state.experiences[0].bullet_points]
        compiled.append(ids)
        pdf = tex_path.with_suffix(".pdf")
        if "bad" in ids:
            pdf.write_bytes(b"incomplete PDF")
            raise ResumeCompileError("Fixture compile failed")
        writer = PdfWriter()
        for _ in range(2 if "large" in ids else 1):
            writer.add_blank_page(width=612, height=792)
        writer.add_metadata({"/Title": ",".join(ids)})
        writer.write(pdf)
        return pdf

    monkeypatch.setattr(build, "render_resume", render)
    monkeypatch.setattr(build, "compile_resume", compile)
    monkeypatch.setattr(build, "_clean_latex_artifacts", lambda _: None)
    tex, resume = render(draft=draft, output_dir=tmp_path, output_name="resume")
    pdf = compile(tex_path=tex, output_dir=tmp_path)
    (tmp_path / "draft.json").write_text(draft.model_dump_json(indent=2))
    compiled.clear()

    def run(candidates, max_attempts=6):
        llm = SimpleNamespace(suggest_additions=lambda **kwargs: candidates)
        build._backfill_resume(
            config=config, draft=draft, resume=resume, job=JobContext(description="Python"),
            llm=llm, template_path=Path("unused"), output_dir=tmp_path, # type: ignore
            output_name="resume", tex_path=tex, pdf_path=pdf,
            max_pages=1, max_attempts=max_attempts,
        )
        return pdf

    return SimpleNamespace(run=run, compiled=compiled, root=tmp_path, pdf=pdf, tex=tex)


def assert_saved_bullets(trial, expected):
    draft = loads((trial.root / "draft.json").read_text())
    tex = loads(trial.tex.read_text())
    assert draft == tex
    assert [b["id"] for b in draft["experiences"][0]["bullet_points"]] == expected
    pdf = PdfReader(trial.pdf)
    assert len(pdf.pages) == 1
    assert pdf.metadata is not None
    assert pdf.metadata.title == ",".join(expected)


def test_overflow_then_acceptance_then_overflow_restores_last_fit(trial_build):
    trial_build.run([addition("large"), addition("small"), addition("large")])
    assert len(trial_build.compiled) == 3
    assert_saved_bullets(trial_build, ["selected", "small"])


def test_failed_compile_and_invalid_candidate_do_not_block_later_addition(trial_build):
    trial_build.run([addition("missing"), addition("bad"), addition("small")])
    assert len(trial_build.compiled) == 2
    assert_saved_bullets(trial_build, ["selected", "small"])


def test_all_rejected_keeps_exact_original_files(trial_build):
    paths = [trial_build.tex, trial_build.pdf, trial_build.root / "draft.json"]
    original = {path: path.read_bytes() for path in paths}
    trial_build.run([addition("large"), addition("bad")])
    assert {path: path.read_bytes() for path in paths} == original


def test_attempt_limit_is_enforced(trial_build):
    trial_build.run([addition("large"), addition("small")], max_attempts=1)
    assert len(trial_build.compiled) == 1
    assert_saved_bullets(trial_build, ["selected"])


def test_duplicate_proposal_is_not_inserted_twice(trial_build):
    trial_build.run([addition("small"), addition("small")])
    assert len(trial_build.compiled) == 1
    assert_saved_bullets(trial_build, ["selected", "small"])


def test_unexpected_failure_restores_files_before_propagating(trial_build, monkeypatch):
    def broken_compile(**kwargs):
        trial_build.pdf.write_bytes(b"broken")
        raise RuntimeError("Unexpected fixture failure")
    monkeypatch.setattr(build, "compile_resume", broken_compile)
    with pytest.raises(RuntimeError):
        trial_build.run([addition("small")])
    assert_saved_bullets(trial_build, ["selected"])


def test_optional_planning_failure_preserves_valid_build(config, draft, trial_build, monkeypatch, caplog):
    def fail(**kwargs):
        raise ResumeLLMError("Model unavailable")
    llm = SimpleNamespace(suggest_additions=fail)
    (trial_build.root / "error.json").write_text('{"type":"old_failure"}')
    result = build.build_resume(
        config=config, draft=draft, job=JobContext(description="Python"), llm=llm, # type: ignore
        template_path=Path("unused"), output_dir=trial_build.root,
    )
    assert result == trial_build.pdf
    assert_saved_bullets(trial_build, ["selected"])
    assert "backfill skipped" in caplog.text
    assert not (trial_build.root / "error.json").exists()


def test_backfill_can_be_disabled(config, draft, trial_build):
    build.build_resume(
        config=config, draft=draft, job=JobContext(description="Python"), llm=object(), # type: ignore
        template_path=Path("unused"), output_dir=trial_build.root, max_backfill_attempts=0,
    )
    assert_saved_bullets(trial_build, ["selected"])


@pytest.mark.parametrize("extra_args, expected_budget", [([], 6), (["--max-backfill-attempts", "0"], 0)])
def test_cli_saved_draft_skips_initial_selection(config, draft, tmp_path, monkeypatch, extra_args, expected_budget):
    from typer.testing import CliRunner
    from resume import cli

    saved = tmp_path / "saved.json"
    saved.write_text(draft.model_dump_json())
    output_dir = tmp_path / "build"
    calls = []
    # This object deliberately has no create_draft method.
    llm = object()
    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    monkeypatch.setattr(cli, "load_resume_config", lambda _: config)
    monkeypatch.setattr(cli, "OpenAIResumeLLM", lambda model: llm)

    def fake_build(**kwargs):
        calls.append(kwargs)
        return kwargs["output_dir"] / "resume.pdf"

    monkeypatch.setattr(cli, "build_resume", fake_build)
    result = CliRunner().invoke(cli.app, [
        "--jd", "Python engineering", "--draft-file", str(saved),
        "--output-dir", str(output_dir), *extra_args,
    ])
    assert result.exit_code == 0, result.output
    assert len(calls) == 1
    assert calls[0]["draft"] == draft
    assert calls[0]["llm"] is llm
    assert calls[0]["max_backfill_attempts"] == expected_budget
    assert ResumeDraft.model_validate_json((output_dir / "draft.json").read_text()) == draft


def test_cli_rejects_negative_backfill_budget():
    from typer.testing import CliRunner
    from resume import cli

    result = CliRunner().invoke(cli.app, ["--jd", "Python", "--max-backfill-attempts", "-1"])
    assert result.exit_code == 2
    assert "--max-backfill-attempts" in result.output
