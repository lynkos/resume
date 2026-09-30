from pathlib import Path

import pytest

from resume.render import resolve_resume
from resume.config import load_job_description, load_resume_config
from resume.models import (
    BulletPointDraft,
    EntryDraft,
    ResumeDraft,
    Section,
    SkillCategory,
)


def _config():
    return load_resume_config(Path(__file__).parents[1] / "resume.example.yaml")


def test_job_description_string_and_path(tmp_path: Path) -> None:
    assert load_job_description("  hello  ") == "hello"
    path = tmp_path / "job.txt"
    path.write_text("  world  ", encoding="utf-8")
    assert load_job_description(path) == "world"


def test_section_order_must_contain_all_sections_once() -> None:
    with pytest.raises(ValueError):
        ResumeDraft(
            section_order=[Section.EXPERIENCE, Section.PROJECTS, Section.SKILLS, Section.SKILLS],
            experiences=[],
            projects=[],
            skills=[],
        )


def test_duplicate_skill_across_categories_rejected() -> None:
    with pytest.raises(ValueError):
        ResumeDraft(
            section_order=list(Section),
            experiences=[],
            projects=[],
            skills=[
                SkillCategory(name="Languages", skills=["Python"]),
                SkillCategory(name="Tools", skills=["Python"]),
            ],
        )


def test_resolve_variant_and_generated_rewrite() -> None:
    draft = ResumeDraft(
        section_order=[
            Section.EXPERIENCE,
            Section.PROJECTS,
            Section.SKILLS,
            Section.EDUCATION,
        ],
        experiences=[
            EntryDraft(
                id="oci",
                bullet_points=[
                    BulletPointDraft(id="release_automation", variant="infra"),
                    BulletPointDraft(id="observability", rewrite="Generated \\textbf{Python} rewrite"),
                ],
            )
        ],
        projects=[
            EntryDraft(
                id="mac_windows",
                bullet_points=[BulletPointDraft(id="launcher")],
            )
        ],
        skills=[SkillCategory(name="Languages", skills=["Python", "Bash"])],
        include_relevant_courses=False,
    )

    resume = resolve_resume(_config(), draft)

    assert resume.experiences[0].bullet_points[0].variant == "infra"
    assert resume.experiences[0].bullet_points[0].generated is False
    assert resume.experiences[0].bullet_points[1].generated is True
    assert resume.education.relevant_courses is None
