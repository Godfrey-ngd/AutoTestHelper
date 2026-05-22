"""JSON file persistence for projects."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from autotestdesign.models.schemas import Project

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "projects"


class ProjectStore:
    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = base_dir or DATA_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, project_id: str) -> Path:
        return self.base_dir / f"{project_id}.json"

    def save(self, project: Project) -> None:
        self._path(project.id).write_text(
            project.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def load(self, project_id: str) -> Optional[Project]:
        path = self._path(project_id)
        if not path.exists():
            return None
        return Project.model_validate_json(path.read_text(encoding="utf-8"))

    def list_ids(self) -> list[str]:
        return [p.stem for p in self.base_dir.glob("*.json")]

    def delete(self, project_id: str) -> bool:
        path = self._path(project_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def export_json(self, project: Project) -> str:
        return json.dumps(project.model_dump(mode="json"), indent=2, ensure_ascii=False)
