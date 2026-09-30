from __future__ import annotations
from pathlib import Path
from typing import Any
from yaml import safe_load
from .models import ResumeConfig


def load_resume_config(path: Path) -> ResumeConfig:
    with path.open("r", encoding="utf-8") as file:
        raw: Any = safe_load(file)

    if not isinstance(raw, dict):
        raise ValueError(f"Resume config must be a YAML mapping: {path}")

    return ResumeConfig.model_validate(raw)


def load_job_description(value: str | Path) -> str:
    if isinstance(value, Path):
        text = value.read_text(encoding="utf-8")
    else: text = value

    text = text.strip()
    
    if not text:
        raise ValueError("Job description cannot be empty")
    
    return text