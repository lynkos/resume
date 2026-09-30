from __future__ import annotations
from openai import OpenAI, OpenAIError
from os import getenv
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from .error import ResumeLLMError
from .models import (
    EntryDraft,
    EntryType,
    BulletPointDraft,
    JobContext,
    Resume,
    ResumeConfig,
    ResumeDraft,
)
from .prompts import (
    ADJUST_INSTRUCTIONS,
    TAILOR_INSTRUCTIONS,
    build_adjustment_prompt,
    build_tailoring_prompt,
    BACKFILL_INSTRUCTIONS,
    build_backfill_prompt,
)


_NonBlankText = Annotated[str, Field(pattern=r"\S")]


class _LLMModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _ChangeVariant(_LLMModel):
    entry_type: EntryType
    entry_id: _NonBlankText
    bullet_id: _NonBlankText
    action: Literal["change_variant"]
    variant: _NonBlankText | None = Field(description="Use null for the bullet's configured default text, or an exact key from its variants mapping.")


class _RewriteBullet(_LLMModel):
    entry_type: EntryType
    entry_id: _NonBlankText
    bullet_id: _NonBlankText
    action: Literal["rewrite_bullet"]
    rewrite: _NonBlankText


class _RemoveBullet(_LLMModel):
    entry_type: EntryType
    entry_id: _NonBlankText
    bullet_id: _NonBlankText
    action: Literal["remove_bullet"]


class _RemoveRelevantCourses(_LLMModel):
    action: Literal["remove_relevant_courses"]


class _RemoveEntry(_LLMModel):
    entry_type: EntryType
    entry_id: _NonBlankText
    action: Literal["remove_entry"]


class _RemoveSkill(_LLMModel):
    action: Literal["remove_skill"]
    category: _NonBlankText
    skill: _NonBlankText


_ResumeAdjustment = (_ChangeVariant | _RewriteBullet | _RemoveBullet | _RemoveRelevantCourses | _RemoveEntry | _RemoveSkill)


class _AdjustmentResponse(_LLMModel):
    # Structured Outputs requires an object at the root; the union is nested.
    adjustment: _ResumeAdjustment


class _ReductionResponse(_LLMModel):
    adjustment: _RemoveBullet | _RemoveRelevantCourses | _RemoveEntry | _RemoveSkill


class _BulletAddition(_LLMModel):
    entry_type: EntryType
    entry_id: _NonBlankText
    bullet_id: _NonBlankText
    variant: _NonBlankText | None = Field(description="Use null for the configured default text, or an exact named variant.")
    after_bullet_id: _NonBlankText | None = Field(description="Insert after this currently selected bullet ID; null appends to the entry.")


class _BackfillPlan(_LLMModel):
    additions: list[_BulletAddition]


class OpenAIResumeLLM:
    def __init__(self, model: str | None = None, client: OpenAI | None = None) -> None:
        selected_model = model or getenv("OPENAI_MODEL")
        
        if not selected_model:
            raise ValueError("Set OPENAI_MODEL in .env or pass model= explicitly")

        self.model = selected_model
        
        if client is None:
            client = OpenAI(api_key = getenv("OPENAI_API_KEY"))
        
        self.client = client

    def create_draft(self, config: ResumeConfig, job: JobContext, *, max_pages: int | None = 1) -> ResumeDraft:
        response = self.client.responses.parse(
            model=self.model,
            instructions=TAILOR_INSTRUCTIONS,
            input=build_tailoring_prompt(config, job, max_pages=max_pages),
            text_format=ResumeDraft,
        )
        
        draft = response.output_parsed
        
        if draft is None:
            raise ResumeLLMError("The model did not return a valid ResumeDraft")
        
        return draft

    def suggest_additions(
        self,
        *,
        config: ResumeConfig,
        draft: ResumeDraft,
        resume: Resume,
        job: JobContext,
        max_candidates: int
    ) -> list[_BulletAddition]:
        prompt = build_backfill_prompt(
            config=config, draft=draft, resume=resume, job=job,
            max_candidates=max_candidates,
        )
        if prompt is None: return []
        
        try:
            response = self.client.responses.parse(
                model=self.model,
                instructions=BACKFILL_INSTRUCTIONS,
                input=prompt,
                text_format=_BackfillPlan,
            )
        except (OpenAIError, ValidationError) as exc:
            raise ResumeLLMError(f"Could not plan resume additions: {exc}") from exc
        
        if response.output_parsed is None:
            raise ResumeLLMError("The model did not return a valid backfill plan")
        
        return response.output_parsed.additions[:max_candidates]

    def adjust_draft_once(
        self,
        *,
        config: ResumeConfig,
        draft: ResumeDraft,
        resume: Resume,
        job: JobContext,
        actual_pages: int,
        max_pages: int,
        allow_rewrite: bool = True,
        max_attempts: int = 3,
    ) -> ResumeDraft:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")

        prompt = build_adjustment_prompt(
            config=config,
            draft=draft,
            resume=resume,
            job=job,
            actual_pages=actual_pages,
            max_pages=max_pages,
            allow_rewrite=allow_rewrite,
        )

        for attempt in range(1, max_attempts + 1):
            response = self.client.responses.parse(
                model=self.model,
                instructions=ADJUST_INSTRUCTIONS,
                input=prompt,
                text_format=_AdjustmentResponse if allow_rewrite else _ReductionResponse,
            )
            parsed = response.output_parsed
            if parsed is None:
                raise ResumeLLMError("The model did not return a valid resume adjustment")

            try:
                return _apply_resume_adjustment(config, draft, parsed.adjustment)
            except ResumeLLMError as exc:
                if attempt == max_attempts:
                    raise ResumeLLMError(f"Could not obtain a valid resume adjustment after {max_attempts} attempts. Last rejection: {exc}") from exc
                prompt += (
                    f"\n\nRejected adjustment:\n{parsed.model_dump_json()}\n"
                    f"Reason: {exc}\n"
                    "The draft has not changed. Choose a different valid adjustment that reduces space; do not repeat a rejected suggestion."
                )

        raise AssertionError("Unreachable")


def _find_entry(draft: ResumeDraft, entry_type: str, entry_id: str) -> EntryDraft:
    entries = draft.experiences if entry_type == "experience" else draft.projects
    try:
        return next(entry for entry in entries if entry.id == entry_id)
    
    except StopIteration as exc:
        raise ResumeLLMError(f"Adjustment targets unknown {entry_type} entry {entry_id!r}") from exc


def _apply_resume_adjustment(config: ResumeConfig, draft: ResumeDraft, adjustment: _ResumeAdjustment) -> ResumeDraft:
    result = draft.model_copy(deep=True) # can i do this w/o deep-copying (or copying in general)?

    if adjustment.action == "remove_relevant_courses":
        if not result.include_relevant_courses:
            raise ResumeLLMError("Relevant Coursework is already hidden")
        result.include_relevant_courses = False
        return ResumeDraft.model_validate(result.model_dump())

    if adjustment.action == "remove_skill":
        category = next((item for item in result.skills if item.name == adjustment.category), None)
        if category is None or adjustment.skill not in category.skills:
            raise ResumeLLMError(f"Adjustment targets unknown selected skill {adjustment.category!r}: {adjustment.skill!r}")
        if sum(len(item.skills) for item in result.skills) <= 1:
            raise ResumeLLMError("Cannot remove the final skill from the Skills section")
        
        category.skills.remove(adjustment.skill)
        if not category.skills:
            result.skills = [item for item in result.skills if item.name != category.name]
        
        return ResumeDraft.model_validate(result.model_dump())

    entry = _find_entry(result, adjustment.entry_type, adjustment.entry_id)
    if adjustment.action == "remove_entry":
        entries = result.experiences if adjustment.entry_type == "experience" else result.projects
        if len(entries) <= 1:
            raise ResumeLLMError(f"Cannot remove the final {adjustment.entry_type} entry")
        remaining = [item for item in entries if item.id != adjustment.entry_id]
        if adjustment.entry_type == "experience":
            result.experiences = remaining
        else:
            result.projects = remaining
        return ResumeDraft.model_validate(result.model_dump())

    try:
        bullet = next(item for item in entry.bullet_points if item.id == adjustment.bullet_id)
    except StopIteration as exc:
        raise ResumeLLMError(f"Adjustment targets unknown bullet {adjustment.entry_id}.{adjustment.bullet_id}") from exc

    config_entries = config.experiences if adjustment.entry_type == "experience" else config.projects
    try:
        config_entry = config_entries[adjustment.entry_id]
        config_bullet = config_entry.bullet_points[adjustment.bullet_id]
    except KeyError as exc:
        raise ResumeLLMError(f"Adjustment target is not present in ResumeConfig: {adjustment.entry_type}.{adjustment.entry_id}.{adjustment.bullet_id}") from exc

    current_text = bullet.rewrite
    if current_text is None:
        current_text = (
            config_bullet.default
            if bullet.variant is None
            else config_bullet.variants[bullet.variant]
        )

    if adjustment.action == "change_variant":
        variant = adjustment.variant
        
        # Accept the model's common label for the canonical text without
        # shadowing an explicitly configured variant named "default".
        # ?
        if variant == "default" and variant not in config_bullet.variants:
            variant = None
        if variant is not None and variant not in config_bullet.variants:
            raise ResumeLLMError(f"Unknown variant {variant!r} for {adjustment.entry_id}.{adjustment.bullet_id}. Use null for the default text or one of {list(config_bullet.variants)!r}")
        
        next_text = config_bullet.default if variant is None else config_bullet.variants[variant]
        if next_text.strip() == current_text.strip():
            raise ResumeLLMError("Selected variant produces the same text as the current bullet")
        
        bullet.variant = variant
        bullet.rewrite = None

    elif adjustment.action == "rewrite_bullet":
        rewrite = adjustment.rewrite.strip()
        if rewrite == current_text.strip():
            raise ResumeLLMError("Rewrite produces the same text as the current bullet")
        bullet.rewrite = rewrite

    elif adjustment.action == "remove_bullet":
        if len(entry.bullet_points) <= 1:
            raise ResumeLLMError("MVP will not remove the final bullet from an entry")
        entry.bullet_points = [item for item in entry.bullet_points if item.id != adjustment.bullet_id]

    return ResumeDraft.model_validate(result.model_dump())


def apply_bullet_addition(config: ResumeConfig, draft: ResumeDraft, addition: _BulletAddition) -> ResumeDraft:
    result = draft.model_copy(deep=True)
    
    entry = _find_entry(result, addition.entry_type, addition.entry_id)
    if any(bullet.id == addition.bullet_id for bullet in entry.bullet_points):
        raise ResumeLLMError(f"Bullet already selected: {addition.entry_id}.{addition.bullet_id}")
    
    sources = config.experiences if addition.entry_type == "experience" else config.projects
    try:
        source = sources[addition.entry_id].bullet_points[addition.bullet_id]
    except KeyError as exc:
        raise ResumeLLMError(f"Unknown source bullet: {addition.entry_id}.{addition.bullet_id}") from exc
    
    variant = addition.variant
    if variant == "default": # and variant not in source.variants:
        variant = None
    if variant is not None and variant not in source.variants:
        raise ResumeLLMError(f"Unknown variant {variant!r} for {addition.entry_id}.{addition.bullet_id}")
    
    index = len(entry.bullet_points)
    if addition.after_bullet_id is not None:
        try:
            index = next(i for i, bullet in enumerate(entry.bullet_points)
                         if bullet.id == addition.after_bullet_id) + 1
        except StopIteration as exc:
            raise ResumeLLMError(f"Insertion target is not selected: {addition.after_bullet_id}") from exc
    
    entry.bullet_points.insert(index, BulletPointDraft(id=addition.bullet_id, variant=variant))
    
    return ResumeDraft.model_validate(result.model_dump())