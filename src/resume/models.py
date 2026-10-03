from __future__ import annotations
from enum import StrEnum
from typing import TypeAlias, Literal
from pydantic import BaseModel, Field, model_validator
from .debug import debug

Skill: TypeAlias = str
EntryType: TypeAlias = Literal["experience", "project"]

class Section(StrEnum):
    EDUCATION = "Education"
    EXPERIENCE = "Experience"
    PROJECTS = "Projects"
    SKILLS = "Skills"


class JobContext(BaseModel):
    description: str = Field(min_length = 1)
    title: str | None = None
    company: str | None = None


class BulletPointConfig(BaseModel):
    default: str = Field(min_length = 1)
    variants: dict[str, str] = Field(default_factory = dict)


class ExperienceConfig(BaseModel):
    title: str
    company: str
    date: str
    location: str | None = None
    technologies: list[Skill] = Field(default_factory = list)
    bullet_points: dict[str, BulletPointConfig]


class ProjectConfig(BaseModel):
    name: str
    date: str
    context: str | None = None
    location: str | None = None
    technologies: list[Skill] = Field(default_factory = list)
    bullet_points: dict[str, BulletPointConfig]


class EducationConfig(BaseModel):
    institution: str
    degree: str
    date: str
    location: str | None = None
    relevant_courses: str | None = None


class ResumeConfig(BaseModel):
    experiences: dict[str, ExperienceConfig]
    projects: dict[str, ProjectConfig]
    skills: list[Skill]
    education: EducationConfig

    @model_validator(mode = "after")
    @debug.trace
    def validate_skill_inventory(self) -> "ResumeConfig":
        if len(self.skills) != len(set(self.skills)):
            raise ValueError("ResumeConfig.skills must not contain duplicates")
        return self


class BulletPointDraft(BaseModel):
    id: str
    variant: str | None = None
    rewrite: str | None = None


class EntryDraft(BaseModel):
    id: str
    bullet_points: list[BulletPointDraft]

    @model_validator(mode = "after")
    @debug.trace
    def validate_bullet_ids(self) -> "EntryDraft":
        ids = [bullet.id for bullet in self.bullet_points]
        if len(ids) != len(set(ids)):
            raise ValueError(f"EntryDraft {self.id!r} contains duplicate bullet IDs")
        return self


class SkillCategory(BaseModel):
    name: str
    skills: list[Skill]

    @model_validator(mode = "after")
    @debug.trace
    def validate_skills(self) -> "SkillCategory":
        if len(self.skills) != len(set(self.skills)):
            raise ValueError(f"Skill category {self.name!r} contains duplicate skills")
        return self


class ResumeDraft(BaseModel):
    section_order: list[Section]
    experiences: list[EntryDraft]
    projects: list[EntryDraft]
    skills: list[SkillCategory]
    include_relevant_courses: bool = False

    @model_validator(mode = "after")
    @debug.trace
    def validate_draft(self) -> "ResumeDraft":
        if len(self.section_order) != len(Section) or set(self.section_order) != set(Section):
            raise ValueError("section_order must contain Education, Experience, Projects, and Skills exactly once")

        experience_ids = [entry.id for entry in self.experiences]
        if len(experience_ids) != len(set(experience_ids)):
            raise ValueError("experiences must not contain duplicate entry IDs")

        project_ids = [entry.id for entry in self.projects]
        if len(project_ids) != len(set(project_ids)):
            raise ValueError("projects must not contain duplicate entry IDs")

        category_names = [category.name for category in self.skills]
        if len(category_names) != len(set(category_names)):
            raise ValueError("skills must not contain duplicate category names")

        all_skills = [skill for category in self.skills for skill in category.skills]
        if len(all_skills) != len(set(all_skills)):
            raise ValueError("a skill may appear only once across the Skills section")

        return self


class BulletPoint(BaseModel):
    id: str
    text: str
    variant: str | None = None
    generated: bool = False


class Experience(BaseModel):
    id: str
    title: str
    company: str
    date: str
    location: str | None = None
    bullet_points: list[BulletPoint]


class Project(BaseModel):
    id: str
    name: str
    date: str
    context: str | None = None
    location: str | None = None
    bullet_points: list[BulletPoint]


class Education(BaseModel):
    institution: str
    degree: str
    date: str
    location: str | None = None
    relevant_courses: str | None = None


class Skills(BaseModel):
    categories: list[SkillCategory]


class Resume(BaseModel):
    section_order: list[Section]
    experiences: list[Experience]
    projects: list[Project]
    skills: Skills
    education: Education