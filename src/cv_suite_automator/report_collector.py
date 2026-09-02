"""Ownership-aware collection of CV Suite HTML reports."""

from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path


class ReportTransferError(RuntimeError):
    """Raised when an owned report cannot be safely transferred."""


@dataclass(frozen=True)
class ReportSnapshot:
    files: frozenset[Path]
    directories: frozenset[Path]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ReportCollector:
    """Track and transfer only reports created during automated tests."""

    def __init__(self, source: str | Path) -> None:
        self.source = Path(source)
        self.owned_files: set[Path] = set()
        self.owned_directories: set[Path] = set()
        self._destinations: dict[Path, Path] = {}

    def snapshot(self) -> ReportSnapshot:
        if not self.source.exists():
            return ReportSnapshot(frozenset(), frozenset())
        files = frozenset(
            path.relative_to(self.source)
            for path in self.source.rglob("*")
            if path.is_file() and path.suffix.casefold() == ".html"
        )
        directories = frozenset(
            path.relative_to(self.source)
            for path in self.source.rglob("*")
            if path.is_dir()
        )
        return ReportSnapshot(files, directories)

    def capture_since(self, before: ReportSnapshot) -> set[Path]:
        after = self.snapshot()
        new_files = set(after.files - before.files)
        self.owned_files.update(new_files)
        self.owned_directories.update(after.directories - before.directories)
        return new_files

    @staticmethod
    def _ensure_destination(destination: Path, fallback: Path | None) -> Path:
        try:
            destination.mkdir(parents=True, exist_ok=True)
            return destination
        except OSError as exc:
            if fallback is None:
                raise ReportTransferError(
                    f"Report destination is unavailable: {destination}: {exc}"
                ) from exc
            try:
                fallback.mkdir(parents=True, exist_ok=True)
                return fallback
            except OSError as fallback_exc:
                raise ReportTransferError(
                    f"Report destination and fallback are unavailable: "
                    f"{destination}; {fallback}"
                ) from fallback_exc

    def _destination_for(
        self, relative_path: Path, destination: Path, archive: Path
    ) -> Path:
        assigned = self._destinations.get(relative_path)
        if assigned is not None and assigned.parent == destination:
            return assigned

        candidate = destination / relative_path.name
        counter = 1
        while (
            candidate.exists()
            or (archive / candidate.name).exists()
            or candidate in self._destinations.values()
        ):
            candidate = destination / (
                f"{relative_path.stem}_{counter}{relative_path.suffix}"
            )
            counter += 1
        self._destinations[relative_path] = candidate
        return candidate

    @staticmethod
    def _verified_copy(source: Path, target: Path) -> None:
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            if not target.exists():
                shutil.copy2(source, temporary)
                if (
                    temporary.stat().st_size != source.stat().st_size
                    or _sha256(temporary) != _sha256(source)
                ):
                    raise ReportTransferError(
                        f"Verification failed for report copy: {source}"
                    )
                os.replace(temporary, target)
            elif (
                target.stat().st_size != source.stat().st_size
                or _sha256(target) != _sha256(source)
            ):
                raise ReportTransferError(
                    f"Existing report copy does not match source: {target}"
                )
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def transfer(
        self,
        destination: str | Path,
        archive: str | Path,
        fallback: str | Path | None = None,
    ) -> None:
        """Back up owned reports externally, then retain them in a local archive."""
        target_root = self._ensure_destination(
            Path(destination), Path(fallback) if fallback is not None else None
        )
        archive_root = self._ensure_destination(Path(archive), None)

        for relative_path in sorted(self.owned_files, key=str):
            source_path = self.source / relative_path
            target_path = self._destination_for(
                relative_path, target_root, archive_root
            )
            archive_path = archive_root / target_path.name
            if not source_path.exists():
                continue

            try:
                self._verified_copy(source_path, target_path)
                self._verified_copy(source_path, archive_path)
                source_path.unlink()
            except ReportTransferError:
                raise
            except OSError as exc:
                raise ReportTransferError(
                    f"Could not transfer report {source_path} to {target_path}: {exc}"
                ) from exc

        for relative_directory in sorted(
            self.owned_directories,
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            try:
                (self.source / relative_directory).rmdir()
            except OSError:
                # Non-empty, removed already, or otherwise not safe to remove.
                pass
