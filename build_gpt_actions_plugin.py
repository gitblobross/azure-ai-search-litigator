#!/usr/bin/env python3
"""Generate GPT Builder plugin files from gpt_actions.json.
Writes openapi.json and ai-plugin.json under .well-known/gpt.
"""

import argparse
import json
import os
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--base-url", default=os.getenv("PLUGIN_BASE_URL", "http://localhost:8000"))
parser.add_argument("--out-dir", default=".well-known/gpt")
args = parser.parse_args()

ROOT = Path(__file__).resolve().parent.parent
ACTIONS_PATH = ROOT / "gpt_actions.json"
actions = json.load(open(ACTIONS_PATH))

# Static schema snippets extracted from the full API spec
SCHEMAS = {
    "MotionResponseRequest": {
        "type": "object",
        "properties": {
            "facts": {"type": "array", "items": {"type": "string"}, "title": "Facts"},
            "claims": {"type": "array", "items": {"type": "string"}, "title": "Claims"},
            "motion_type": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "title": "Motion Type",
                "default": "Motion to Dismiss",
            },
        },
        "required": ["facts", "claims"],
        "title": "MotionResponseRequest",
    },
    "FactExtractRequest": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "title": "Text"},
            "context": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "title": "Context",
            },
            "extract_metadata": {
                "anyOf": [{"type": "boolean"}, {"type": "null"}],
                "title": "Extract Metadata",
                "default": False,
            },
            "confidence_threshold": {
                "anyOf": [{"type": "number"}, {"type": "null"}],
                "title": "Confidence Threshold",
                "default": 0.5,
            },
        },
        "required": ["text"],
        "title": "FactExtractRequest",
        "description": "Request model for extracting facts from text",
    },
    "FactResponse": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "title": "Text"},
            "date": {"anyOf": [{"type": "string"}, {"type": "null"}], "title": "Date"},
            "tags": {
                "anyOf": [
                    {"type": "array", "items": {"type": "string"}},
                    {"type": "null"},
                ],
                "title": "Tags",
            },
            "para": {"anyOf": [{"type": "integer"}, {"type": "null"}], "title": "Para"},
            "source": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "title": "Source",
            },
            "statutes_referenced": {
                "anyOf": [
                    {"type": "array", "items": {"type": "string"}},
                    {"type": "null"},
                ],
                "title": "Statutes Referenced",
            },
            "supported_causes": {
                "anyOf": [
                    {"type": "array", "items": {"type": "string"}},
                    {"type": "null"},
                ],
                "title": "Supported Causes",
            },
            "related_claims": {
                "anyOf": [
                    {"type": "array", "items": {"type": "string"}},
                    {"type": "null"},
                ],
                "title": "Related Claims",
            },
            "related_exhibits": {
                "anyOf": [
                    {"type": "array", "items": {"type": "integer"}},
                    {"type": "null"},
                ],
                "title": "Related Exhibits",
            },
            "id": {"type": "integer", "title": "Id"},
            "timestamp": {
                "type": "string",
                "format": "date-time",
                "title": "Timestamp",
            },
            "related_facts": {
                "anyOf": [
                    {"type": "array", "items": {"type": "integer"}},
                    {"type": "null"},
                ],
                "title": "Related Facts",
            },
            "related_rebuttals": {
                "anyOf": [
                    {"type": "array", "items": {"type": "integer"}},
                    {"type": "null"},
                ],
                "title": "Related Rebuttals",
            },
            "related_legal_elements": {
                "anyOf": [
                    {"type": "array", "items": {"type": "integer"}},
                    {"type": "null"},
                ],
                "title": "Related Legal Elements",
            },
            "related_causes": {
                "anyOf": [
                    {"type": "array", "items": {"type": "integer"}},
                    {"type": "null"},
                ],
                "title": "Related Causes",
            },
            "related_complaint_id": {
                "anyOf": [{"type": "integer"}, {"type": "null"}],
                "title": "Related Complaint Id",
            },
        },
        "required": ["text", "id", "timestamp"],
        "title": "FactResponse",
    },
    "FactExtractResponse": {
        "type": "object",
        "properties": {
            "facts": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/FactResponse"},
                "title": "Facts",
            },
            "confidence_scores": {
                "type": "object",
                "additionalProperties": {"type": "number"},
                "title": "Confidence Scores",
            },
            "metadata": {
                "anyOf": [
                    {"type": "object", "additionalProperties": True},
                    {"type": "null"},
                ],
                "title": "Metadata",
            },
            "extraction_summary": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "title": "Extraction Summary",
            },
        },
        "required": ["facts", "confidence_scores"],
        "title": "FactExtractResponse",
        "description": "Response model for fact extraction results",
    },
    "LegalElementResponse": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "title": "Name"},
            "cause_id": {"type": "integer", "title": "Cause Id"},
            "description": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "title": "Description",
            },
            "id": {"type": "integer", "title": "Id"},
            "facts": {
                "anyOf": [
                    {"type": "array", "items": {"type": "integer"}},
                    {"type": "null"},
                ],
                "title": "Facts",
            },
        },
        "required": ["name", "cause_id", "id"],
        "title": "LegalElementResponse",
    },
    "LegalElementsResponse": {
        "type": "object",
        "properties": {
            "legalElements": {
                "type": "object",
                "additionalProperties": {
                    "type": "array",
                    "items": {"$ref": "#/components/schemas/LegalElementResponse"},
                },
                "title": "Legalelements",
            },
        },
        "required": ["legalElements"],
        "title": "LegalElementsResponse",
    },
}

spec = {
    "openapi": "3.1.0",
    "info": {
        "title": "Litigator GPT Actions",
        "version": "1.0.0",
        "description": "Minimal plugin for evidence upload, fact extraction, drafting, and RAG queries.",
    },
    "servers": [{"url": args.base_url}],
    "paths": {},
    "components": {"schemas": {}},
}

refs = set()


def add_refs(schema):
    if isinstance(schema, dict):
        if "$ref" in schema:
            refs.add(schema["$ref"].split("/")[-1])
        for v in schema.values():
            add_refs(v)
    elif isinstance(schema, list):
        for item in schema:
            add_refs(item)


for op in actions:
    path_item = spec["paths"].setdefault(op["path"], {})
    method = op["method"].lower()
    op_spec = {
        "operationId": op["operationId"],
        "responses": {
            "200": {
                "description": "Successful Response",
                "content": {"application/json": {"schema": op["responseSchema"]}},
            }
        },
    }
    if op["method"].upper() != "GET":
        op_spec["requestBody"] = {
            "content": {"application/json": {"schema": op["requestSchema"]}},
            "required": True,
        }
    path_item[method] = op_spec
    add_refs(op["requestSchema"])
    add_refs(op["responseSchema"])

for name in refs:
    if name in SCHEMAS:
        spec["components"]["schemas"][name] = SCHEMAS[name]

out_dir = ROOT / args.out_dir
out_dir.mkdir(parents=True, exist_ok=True)

with open(out_dir / "openapi.json", "w") as f:
    json.dump(spec, f, indent=2)

manifest = {
    "schema_version": "v1",
    "name_for_human": "Litigator GPT",
    "name_for_model": "litigator_gpt",
    "description_for_human": "Upload evidence, extract facts and draft legal texts.",
    "description_for_model": "Manage evidence and facts, run RAG queries and draft motions.",
    "auth": {"type": "none"},
    "api": {"type": "openapi", "url": f"{args.base_url}/{args.out_dir}/openapi.json"},
    "logo_url": f"{args.base_url}/static/logo.png",
    "contact_email": "support@example.com",
    "legal_info_url": f"{args.base_url}/legal",
}

with open(out_dir / "ai-plugin.json", "w") as f:
    json.dump(manifest, f, indent=2)

print(f"✓ Plugin files written to {out_dir}")
