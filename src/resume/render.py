from pathlib import Path
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from .debug import debug
from .models import (
    BulletPoint,
    BulletPointConfig,
    BulletPointDraft,
    Education,
    Experience,
    Project,
    Resume,
    ResumeConfig,
    ResumeDraft,
    Skills
)


@debug.trace
def _resolve_bullet(config: BulletPointConfig, draft: BulletPointDraft) -> BulletPoint:
    debug.print("Resolve bullet", bullet_id=draft.id, variant=draft.variant, rewritten=draft.rewrite is not None)
    if draft.variant is not None and draft.variant not in config.variants:
        raise ValueError(f"Unknown bullet variant: {draft.variant!r}")

    if draft.rewrite is not None:
        text = draft.rewrite
        generated = True
    
    elif draft.variant is not None:
        text = config.variants[draft.variant]
        generated = False
    
    else:
        text = config.default
        generated = False

    debug.dump("Resolved bullet text", text)
    return BulletPoint(
        id=draft.id,
        text=text,
        variant=draft.variant,
        generated=generated,
    )


@debug.trace
def resolve_resume(config: ResumeConfig, draft: ResumeDraft) -> Resume:
    debug.print("Resolve resume", section_order=draft.section_order, experiences=len(draft.experiences), projects=len(draft.projects))
    experiences: list[Experience] = []
    
    for entry in draft.experiences:
        debug.print("Resolve experience entry", entry_id=entry.id, bullets=len(entry.bullet_points))
        if entry.id not in config.experiences:
            raise ValueError(f"Unknown experience ID: {entry.id!r}")
        
        source = config.experiences[entry.id]
        bullets: list[BulletPoint] = []
        for bullet_draft in entry.bullet_points:
            if bullet_draft.id not in source.bullet_points:
                raise ValueError(f"Unknown experience bullet: {entry.id}.{bullet_draft.id}")
            bullets.append(_resolve_bullet(source.bullet_points[bullet_draft.id], bullet_draft))
        
        experiences.append(
            Experience(
                id=entry.id,
                title=source.title,
                company=source.company,
                date=source.date,
                location=source.location,
                bullet_points=bullets,
            )
        )

    projects: list[Project] = []
    for entry in draft.projects:
        debug.print("Resolve project entry", entry_id=entry.id, bullets=len(entry.bullet_points))
        if entry.id not in config.projects:
            raise ValueError(f"Unknown project ID: {entry.id!r}")
        
        source = config.projects[entry.id]
        bullets: list[BulletPoint] = []
        for bullet_draft in entry.bullet_points:
            if bullet_draft.id not in source.bullet_points:
                raise ValueError(f"Unknown project bullet: {entry.id}.{bullet_draft.id}")
            bullets.append(_resolve_bullet(source.bullet_points[bullet_draft.id], bullet_draft))
        
        projects.append(
            Project(
                id=entry.id,
                name=source.name,
                date=source.date,
                context=source.context,
                location=source.location,
                bullet_points=bullets,
            )
        )

    selected_skills = [skill for category in draft.skills for skill in category.skills]
    debug.print("Validate selected skills", categories=len(draft.skills), skills=len(selected_skills))
    unknown_skills = set(selected_skills) - set(config.skills)
    if unknown_skills:
        raise ValueError(f"ResumeDraft contains unknown skills: {', '.join(unknown_skills)}")

    relevant_courses = (config.education.relevant_courses if draft.include_relevant_courses else None)
    debug.print("Resolve education", include_relevant_courses=draft.include_relevant_courses)
    if draft.include_relevant_courses and not relevant_courses:
        raise ValueError("ResumeDraft requests Relevant Coursework, but none is configured")

    education = Education(
        institution=config.education.institution,
        degree=config.education.degree,
        date=config.education.date,
        location=config.education.location,
        relevant_courses=relevant_courses
    )

    return Resume(
        section_order=draft.section_order,
        experiences=experiences,
        projects=projects,
        skills=Skills(categories=draft.skills),
        education=education,
    )


@debug.trace
def _latex_escape(value: str) -> str:
    debug.print("Escape LaTeX text", characters=len(value))
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in value)


@debug.trace
def render_resume(
    *,
    config: ResumeConfig,
    draft: ResumeDraft,
    template_path: Path,
    output_dir: Path,
    output_name: str = "resume"
) -> tuple[Path, Resume]:
    resume = resolve_resume(config, draft)
    #debug.dump("Resolved resume", resume)
    debug.print("Create render output directory", path=output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    debug.print("Create Jinja environment", template_directory=template_path.parent)
    env = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        undefined=StrictUndefined,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["latex_escape"] = _latex_escape
    debug.print("Load Jinja template", path=template_path)
    template = env.get_template(template_path.name)
    with debug.step("Jinja template.render"):
        rendered = template.render(resume=resume)

    tex_path = output_dir / f"{output_name}.tex"
    #debug.dump("Rendered LaTeX", rendered)
    debug.print("Write LaTeX", path=tex_path, characters=len(rendered))
    tex_path.write_text(rendered, encoding="utf-8")
    return tex_path, resume