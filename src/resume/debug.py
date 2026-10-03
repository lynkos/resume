"""Opt-in terminal tracing. Uses Rich printing; no logging configuration or files."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager, nullcontext
from functools import wraps
from json import dumps
from time import perf_counter
from typing import ParamSpec, TypeVar

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

P = ParamSpec("P")
T = TypeVar("T")


class DebugOutput:
    def __init__(self) -> None:
        self.enabled = False
        self.console = Console(stderr=True, markup=False, highlight=False)
        self._depth = 0
        self._started = 0.0

    @contextmanager
    def session(self, enabled: bool = True) -> Iterator[None]:
        """
        Enable tracing for one run, restoring state even if the run fails.

        Args:
            enabled (bool, optional): Whether tracing is enabled. Defaults to True.

        Yields:
            Iterator[None]: Iterator.
        """
        previous = self.enabled, self.console, self._depth, self._started
        self.enabled = enabled
        self.console = Console(stderr=True, markup=False, highlight=False)
        self._depth = 0
        self._started = perf_counter()
        
        try:
            if enabled:
                self.console.rule(Text("Resume debug", style="bold cyan"))
            yield
        finally:
            self.enabled, self.console, self._depth, self._started = previous

    def _write(self, message: str, style: str = "dim") -> None:
        line = Text(f"{perf_counter() - self._started:8.2f}s ", style="dim")
        line.append("  " * self._depth)
        line.append(message, style=style)
        self.console.print(line, soft_wrap=not self.console.is_terminal)

    def print(self, message: str, **details: object) -> None:
        if not self.enabled: return
        fields = "  ".join(f"{key}={value!r}" for key, value in details.items())
        self._write(f"{message}  {fields}" if fields else message)

    def warning(self, message: str) -> None:
        if self.enabled: self._write(f"WARN {message}", "yellow")
        else: print(message) # Preserve existing CLI warnings outside debug mode.

    def dump(self, title: str, value: object) -> None:
        """Print complete text/JSON, treating user and model text literally."""
        if not self.enabled: return
        
        if isinstance(value, str): content = value
        elif hasattr(value, "model_dump_json"): content = value.model_dump_json(indent=2) # type: ignore
        else: content = dumps(value, indent=2, ensure_ascii=False, default=str)
        
        if self.console.is_terminal:
            self.console.print(Panel(Text(content), title=Text(title), border_style="dim"))
        else:
            self._write(title, "cyan")
            self.console.print(Text(content), soft_wrap=True)

    @contextmanager
    def step(self, label: str, *, spinner: bool = False) -> Iterator[None]:
        if not self.enabled:
            yield
            return

        self._write(f"START {label}", "cyan")
        started = perf_counter()
        self._depth += 1
        status = (
            self.console.status(Text(label), spinner="dots")
            if spinner and self.console.is_terminal and not self.console.is_dumb_terminal
            else nullcontext()
        )
        try:
            with status: yield
        except BaseException as exc:
            self._depth -= 1
            self._write(f"FAIL {label} ({perf_counter() - started:.3f}s): {type(exc).__name__}: {exc}", "bold red")
            raise
        else:
            self._depth -= 1
            self._write(f"DONE {label} ({perf_counter() - started:.3f}s)", "green")

    def trace(self, function: Callable[P, T]) -> Callable[P, T]:
        """
        Trace application function entry/exit without printing arbitrary locals.

        Args:
            function (Callable[P, T]): Application function to trace.

        Returns:
            Callable[P, T]: Wrapped function.
        """
        @wraps(function)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
            if not self.enabled:
                return function(*args, **kwargs)
            with self.step(f"{function.__module__}.{function.__qualname__}"):
                return function(*args, **kwargs)

        return wrapped


# One synchronous CLI run shares this printer; it is disabled on import.
debug = DebugOutput()