from __future__ import annotations
from pathlib import Path
from typing import Any
from yaml import safe_load
from .debug import debug
from .models import ResumeConfig


@debug.trace
def load_resume_config(path: Path) -> ResumeConfig:
    debug.print("Read resume YAML", path=path)
    with path.open("r", encoding="utf-8") as file:
        raw: Any = safe_load(file)

    if not isinstance(raw, dict):
        raise ValueError(f"Resume config must be a YAML mapping: {path}")

    debug.print("Validate ResumeConfig")
    config = ResumeConfig.model_validate(raw)
    debug.print("Config loaded", experiences=len(config.experiences), projects=len(config.projects), skills=len(config.skills))
    #debug.dump("Resume configuration", config)
    return config


@debug.trace
def load_job_description(value: str | Path) -> str:
    if isinstance(value, Path):
        debug.print("Read job-description file", path=value)
        text = value.read_text(encoding="utf-8")
    else:
        debug.print("Use literal job description")
        text = value

    text = text.strip()
    
    if not text:
        raise ValueError("Job description cannot be empty")
    
    debug.print("Job description loaded", characters=len(text))
    return text
