"""Optional FastAPI REST API for AutoTestDesign."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from autotestdesign.core.exporters.export import export_csv, export_json_bytes
from autotestdesign.core.pipeline import import_requirements, run_full_pipeline
from autotestdesign.models.schemas import Project
from autotestdesign.storage.project_store import ProjectStore

app = FastAPI(title="AutoTestDesign API", version="1.0.0")
store = ProjectStore()


class ImportBody(BaseModel):
    name: str = "API Project"
    content: str
    source: str = "auto"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/projects")
def create_project(body: ImportBody):
    project = Project(name=body.name)
    project = import_requirements(project, body.content, body.source)
    project, _ = run_full_pipeline(project)
    store.save(project)
    return {"project_id": project.id, "cases": len(project.test_cases)}


@app.get("/projects/{project_id}")
def get_project(project_id: str):
    p = store.load(project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    return p.model_dump(mode="json")


@app.get("/projects/{project_id}/export/json")
def export_json(project_id: str):
    p = store.load(project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    return Response(export_json_bytes(p), media_type="application/json")


@app.get("/projects/{project_id}/export/csv")
def export_csv_endpoint(project_id: str):
    p = store.load(project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    return Response(export_csv(p), media_type="text/csv")
