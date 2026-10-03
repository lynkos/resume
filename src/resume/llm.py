from __future__ import annotations
from openai import OpenAI, OpenAIError
from os import getenv
from typing import Annotated, Literal, TypeVar
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from .debug import debug
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
_Response = TypeVar("_Response", bound=BaseModel)


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
    @debug.trace
    def __init__(self, model: str | None = None, client: OpenAI | None = None) -> None:
        selected_model = model or getenv("OPENAI_MODEL")
        debug.print("Select OpenAI model", model=selected_model, source="argument" if model else "OPENAI_MODEL")
        
        if not selected_model:
            raise ValueError("Set OPENAI_MODEL in .env or pass model= explicitly")

        self.model = selected_model
        
        if client is None:
            debug.print("Create OpenAI client")
            client = OpenAI(api_key = getenv("OPENAI_API_KEY"))
        else: debug.print("Use supplied OpenAI client")
        
        self.client = client

    @debug.trace
    def _request(self, *, instructions: str, prompt: str, text_format: type[_Response]) -> _Response | None:
        debug.print("Prepare structured request", model=self.model, schema=text_format.__name__, prompt_characters=len(prompt))
        #debug.dump("OpenAI instructions", instructions)
        #debug.dump("OpenAI prompt", prompt)
        
        with debug.step("OpenAI responses.parse", spinner=True):
            response = self.client.responses.parse(
                model=self.model,
                instructions=instructions,
                input=prompt,
                text_format=text_format,
            )
            
        parsed = response.output_parsed
        
        if debug.enabled:
            debug.print("OpenAI response", response_id=response.id, status=response.status)
            debug.dump("Token usage", response.usage)
            #debug.dump("Parsed response", parsed)
            
            if parsed is None:
                debug.dump("Unparsed response output", response.output)
                
        return parsed

    @debug.trace
    def create_draft(self, config: ResumeConfig, job: JobContext, *, max_pages: int | None = 1) -> ResumeDraft:
        draft = self._request(
            instructions=TAILOR_INSTRUCTIONS,
            prompt=build_tailoring_prompt(config, job, max_pages=max_pages),
            text_format=ResumeDraft,
        )
        
        if draft is None:
            raise ResumeLLMError("The model did not return a valid ResumeDraft")
        
        return draft

    @debug.trace
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
        if prompt is None:
            debug.print("Skip backfill request: no eligible candidates")
            return []
        
        try:
            parsed = self._request(
                instructions=BACKFILL_INSTRUCTIONS,
                prompt=prompt,
                text_format=_BackfillPlan,
            )
        except (OpenAIError, ValidationError) as exc:
            raise ResumeLLMError(f"Could not plan resume additions: {exc}") from exc
        
        if parsed is None:
            raise ResumeLLMError("The model did not return a valid backfill plan")
        
        debug.print("Limit backfill plan", proposed=len(parsed.additions), maximum=max_candidates)
        return parsed.additions[:max_candidates]

    @debug.trace
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
            debug.print("Adjustment request", attempt=attempt, maximum=max_attempts, allow_rewrite=allow_rewrite)
            parsed = self._request(instructions=ADJUST_INSTRUCTIONS, prompt=prompt, text_format=_AdjustmentResponse if allow_rewrite else _ReductionResponse)
            if parsed is None:
                raise ResumeLLMError("The model did not return a valid resume adjustment")

            try:
                return _apply_resume_adjustment(config, draft, parsed.adjustment)
            except ResumeLLMError as exc:
                debug.print("Reject adjustment", reason=str(exc), attempt=attempt, maximum=max_attempts)
                if attempt == max_attempts:
                    raise ResumeLLMError(f"Could not obtain a valid resume adjustment after {max_attempts} attempts. Last rejection: {exc}") from exc
                debug.print("Append rejection feedback and retry")
                prompt += (
                    f"\n\nRejected adjustment:\n{parsed.model_dump_json()}\n"
                    f"Reason: {exc}\n"
                    "The draft has not changed. Choose a different valid adjustment that reduces space; do not repeat a rejected suggestion."
                )

        raise AssertionError("Unreachable")


@debug.trace
def _find_entry(draft: ResumeDraft, entry_type: str, entry_id: str) -> EntryDraft:
    debug.print("Find selected entry", entry_type=entry_type, entry_id=entry_id)
    entries = draft.experiences if entry_type == "experience" else draft.projects
    
    try:
        return next(entry for entry in entries if entry.id == entry_id)
    
    except StopIteration as exc:
        raise ResumeLLMError(f"Adjustment targets unknown {entry_type} entry {entry_id!r}") from exc


@debug.trace
def _apply_resume_adjustment(config: ResumeConfig, draft: ResumeDraft, adjustment: _ResumeAdjustment) -> ResumeDraft:
    debug.dump("Apply adjustment", adjustment)
    debug.print("Copy draft before adjustment")
    result = draft.model_copy(deep=True) # can i do this w/o deep-copying (or copying in general)?

    if adjustment.action == "remove_relevant_courses":
        if not result.include_relevant_courses:
            raise ResumeLLMError("Relevant Coursework is already hidden")
        result.include_relevant_courses = False
        debug.print("Hide relevant coursework; validate updated draft")
        return ResumeDraft.model_validate(result.model_dump())

    if adjustment.action == "remove_skill":
        debug.print("Find selected skill", category=adjustment.category, skill=adjustment.skill)
        category = next((item for item in result.skills if item.name == adjustment.category), None)
        
        if category is None or adjustment.skill not in category.skills:
            raise ResumeLLMError(f"Adjustment targets unknown selected skill {adjustment.category!r}: {adjustment.skill!r}")
        
        if sum(len(item.skills) for item in result.skills) <= 1:
            raise ResumeLLMError("Cannot remove the final skill from the Skills section")
        
        category.skills.remove(adjustment.skill)
        if not category.skills:
            debug.print("Remove empty skill category", category=category.name)
            result.skills = [item for item in result.skills if item.name != category.name]
        
        debug.print("Skill removed; validate updated draft")
        return ResumeDraft.model_validate(result.model_dump())

    entry = _find_entry(result, adjustment.entry_type, adjustment.entry_id)
    if adjustment.action == "remove_entry":
        entries = result.experiences if adjustment.entry_type == "experience" else result.projects
        
        if len(entries) <= 1:
            raise ResumeLLMError(f"Cannot remove the final {adjustment.entry_type} entry")
        
        remaining = [item for item in entries if item.id != adjustment.entry_id]
        
        if adjustment.entry_type == "experience":
            result.experiences = remaining
        else: result.projects = remaining
        
        debug.print("Entry removed; validate updated draft", entry_type=adjustment.entry_type, entry_id=adjustment.entry_id)
        return ResumeDraft.model_validate(result.model_dump())

    debug.print("Find selected bullet", entry_id=adjustment.entry_id, bullet_id=adjustment.bullet_id)
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
    debug.dump("Current bullet text", current_text)

    if adjustment.action == "change_variant":
        variant = adjustment.variant
        
        # Accept the model's common label for the canonical text without
        # shadowing an explicitly configured variant named "default".
        # ?
        if variant == "default" and variant not in config_bullet.variants:
            debug.print("Normalize default variant label to null")
            variant = None
        if variant is not None and variant not in config_bullet.variants:
            raise ResumeLLMError(f"Unknown variant {variant!r} for {adjustment.entry_id}.{adjustment.bullet_id}. Use null for the default text or one of {list(config_bullet.variants)!r}")
        
        next_text = config_bullet.default if variant is None else config_bullet.variants[variant]
        if next_text.strip() == current_text.strip():
            raise ResumeLLMError("Selected variant produces the same text as the current bullet")
        
        bullet.variant = variant
        bullet.rewrite = None
        debug.print("Change bullet variant", variant=variant)
        debug.dump("Replacement bullet text", next_text)

    elif adjustment.action == "rewrite_bullet":
        rewrite = adjustment.rewrite.strip()
        if rewrite == current_text.strip():
            raise ResumeLLMError("Rewrite produces the same text as the current bullet")
        bullet.rewrite = rewrite
        debug.dump("Replacement bullet text", rewrite)

    elif adjustment.action == "remove_bullet":
        if len(entry.bullet_points) <= 1:
            raise ResumeLLMError("MVP will not remove the final bullet from an entry")
        entry.bullet_points = [item for item in entry.bullet_points if item.id != adjustment.bullet_id]
        debug.print("Remove bullet", bullet_id=adjustment.bullet_id, remaining=len(entry.bullet_points))

    debug.print("Validate adjusted draft")
    return ResumeDraft.model_validate(result.model_dump())


@debug.trace
def apply_bullet_addition(config: ResumeConfig, draft: ResumeDraft, addition: _BulletAddition) -> ResumeDraft:
    debug.dump("Apply bullet addition", addition)
    debug.print("Copy draft before addition")
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
        debug.print("Normalize default variant label to null")
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
    
    debug.print("Insert bullet and validate draft", entry_id=addition.entry_id, bullet_id=addition.bullet_id, index=index, variant=variant)
    return ResumeDraft.model_validate(result.model_dump())