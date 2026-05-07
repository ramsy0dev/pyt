"""Lazy download builder.

The legacy :meth:`pyt.Stream.download` blocks, takes 6 kwargs, and fires
its progress callback through a process-global ``Monostate``. This module
wraps that into a :class:`Download` builder you can compose and re-run
without mutating client state.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional, Union

from pyt.api.errors import DownloadError, PostProcessError

if TYPE_CHECKING:
    from pyt.api.pipeline import PipelineStep
    from pyt.api.streams import StreamRef


PathLike = Union[str, Path]


@dataclass(frozen=True)
class ProgressEvent:
    """Returned to user-supplied callbacks.

    For now only the legacy chunk-based progress is exposed. Once the
    transport moves to httpx we'll add ``Started``, ``Completed``, and
    ``Error`` variants as separate types so callers can pattern-match.
    """

    bytes_done: int
    bytes_total: int
    chunk: bytes


class Download:
    """A planned-but-not-yet-executed download.

    Construct via :meth:`StreamRef.download_to`. Run with ``.run()``, or
    pipe through post-processors with ``.then(...)`` / ``|``.
    """

    def __init__(
        self,
        *,
        stream: "StreamRef",
        output_path: Optional[PathLike] = None,
        filename: Optional[str] = None,
        filename_prefix: Optional[str] = None,
        skip_existing: bool = True,
        timeout: Optional[int] = None,
        max_retries: int = 0,
        steps: Optional[List["PipelineStep"]] = None,
    ):
        self._stream = stream
        self._output_path = str(output_path) if output_path is not None else None
        self._filename = filename
        self._filename_prefix = filename_prefix
        self._skip_existing = skip_existing
        self._timeout = timeout
        self._max_retries = max_retries
        self._steps: List["PipelineStep"] = list(steps or [])

    # ── composition ─────────────────────────────────────────────────────────

    def then(self, *steps: "PipelineStep") -> "Download":
        """Append one or more post-processing steps. Returns a new
        :class:`Download` (the original is not mutated)."""
        return self._replace(steps=self._steps + list(steps))

    def __or__(self, step: "PipelineStep") -> "Download":
        return self.then(step)

    # ── execution ───────────────────────────────────────────────────────────

    def run(self) -> Path:
        """Transfer the bytes to disk, run the pipeline, return the final path."""
        try:
            raw_path = self._stream.legacy.download(
                output_path=self._output_path,
                filename=self._filename,
                filename_prefix=self._filename_prefix,
                skip_existing=self._skip_existing,
                timeout=self._timeout,
                max_retries=self._max_retries,
            )
        except Exception as exc:
            raise DownloadError(
                f"download failed: {exc}",
                video_id=self._stream.video.video_id,
                url=self._stream.video.url,
            ) from exc

        path = raw_path
        for step in self._steps:
            try:
                path = step.apply(path, stream=self._stream, video=self._stream.video)
            except PostProcessError:
                raise
            except Exception as exc:
                raise PostProcessError(
                    f"step '{step.name}' failed: {exc}",
                    step=step.name,
                    partial_output_path=path,
                    cause=exc,
                ) from exc

        return Path(path)

    # ── helpers ─────────────────────────────────────────────────────────────

    def _replace(self, **changes: Any) -> "Download":
        kwargs = dict(
            stream=self._stream,
            output_path=self._output_path,
            filename=self._filename,
            filename_prefix=self._filename_prefix,
            skip_existing=self._skip_existing,
            timeout=self._timeout,
            max_retries=self._max_retries,
            steps=self._steps,
        )
        kwargs.update(changes)
        return Download(**kwargs)

    def __repr__(self) -> str:
        n = len(self._steps)
        return f"<Download stream={self._stream!r} steps={n}>"
