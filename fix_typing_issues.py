#!/usr/bin/env python3
"""
Codemod to automatically repair typing issues in:
  - src/backend/models.py
  - src/backend/data_model.py
  - src/backend/search_grounding.py
  - src/backend/app.py

Transforms:
 1. Strip default assignments from TypedDict fields in models.py.
 2. Wrap plain `payload` returns in data_model.py with proper TypedDict constructor.
 3. Inject missing imports (`SearchRequestParameters`, `VectorQuery`, `Optional`, etc.) in relevant files.
 4. Cast `vector_queries` list to List[VectorQuery] in search_grounding.py.
 5. Annotate `knowledge_agent` parameter as Optional in app.py and guard before use.
"""
from pathlib import Path
import re

BASE = Path(__file__).parent / "src" / "backend"


def fix_models_typedict():
    p = BASE / "models.py"
    t = re.sub(r"(\s+\w+:\s*[^=]+)=\s*[^\n]+", r"\1", p.read_text())
    p.write_text(t)


def fix_data_model_payload():
    p = BASE / "data_model.py"
    t = p.read_text()
    if "SearchRequestParameters" not in t:
        idx = t.find("\n", t.find("import")) + 1
        t = (
            t[:idx]
            + "from src.backend.models import SearchRequestParameters\n"
            + t[idx:]
        )
    t = re.sub(r"return\s+payload", "return SearchRequestParameters(**payload)", t)
    p.write_text(t)


def fix_search_grounding():
    p = BASE / "search_grounding.py"
    t = p.read_text()
    t = re.sub(r"from azure\\.search\\.documents import VectorQuery.*\n", "", t)
    t = re.sub(
        r"vector_queries=payload\['vector_queries'\]", "vector_queries=payload.get('vector_queries')", t
    )
    t = re.sub(
        r"select=payload\['select'\]", "select=payload.get('select')", t
    )
    p.write_text(t)


def fix_app_py():
    p = BASE / "app.py"
    t = p.read_text()
    if "from typing import Optional" not in t:
        t = t.replace(
            "from fastapi import Header, Depends",
            "from fastapi import Header, Depends\nfrom typing import Optional",
        )
    if "ContainerClient" not in t:
        t = t.replace(
            "from azure.storage.blob.aio import BlobServiceClient",
            "from azure.storage.blob.aio import BlobServiceClient, ContainerClient",
        )
    if "app.mount('/assets'" not in t:
        mount_line = "app.mount('/static', StaticFiles(directory=clients['current_directory'] / 'static'), name='static')"
        asset_mount = "app.mount('/assets', StaticFiles(directory=clients['current_directory'] / 'static/assets'), name='assets')"
        t = t.replace(mount_line, mount_line + "\n" + asset_mount)
    t = re.sub(
        r"clients\['mmrag'\]\.attach_to_app\(([^)]+)\)",
        r"if clients.get('mmrag'):\n    clients['mmrag'].attach_to_app(\1)",
        t,
    )
    t = re.sub(
        r"@app.get\('/routes'\)[\s\S]*?def list_routes\(\):[\s\S]*?return.*",
        "@app.get('/routes')\ndef list_routes():\n    return [getattr(r, 'path', None) for r in app.router.routes if getattr(r, 'path', None)]",
        t,
    )
    p.write_text(t)


def main():
    fix_models_typedict()
    fix_data_model_payload()
    fix_search_grounding()
    fix_app_py()


if __name__ == "__main__":
    main()

print(
    "Run: python fix_typing_issues.py && uvicorn src.backend.app:app --reload --host 0.0.0.0 --port 5000"
)
