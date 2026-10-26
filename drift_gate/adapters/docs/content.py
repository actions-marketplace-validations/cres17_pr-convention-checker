"""Collect key-name evidence for configured environment sample documents."""
from dataclasses import replace
from pathlib import Path

from drift_gate.adapters.docs.structured import normalize_openapi_yaml
from drift_gate.adapters.snapshot import read_bounded_text
from drift_gate.core.evaluation.contracts import env_keys_in_document
from drift_gate.core.models.changed_file import ChangedFile
from drift_gate.core.models.changed_file_source import ChangedFileSource


UNAVAILABLE_ERROR = 'Document could not be read or safely decoded'
ENV_DOCUMENT_CONTENT = {"env-keys", "api-schema", "auto-strict", "api-routes", "auto"}
SCHEMA_CONTENT = {"api-schema", "api-routes", "auto-strict", "auto"}


def schema_document_paths(policy):
    return {path for rule in policy.rules for group in rule.require.groups
            if group.content in SCHEMA_CONTENT
            for path in (group.any_changed or group.all_changed)}


def document_paths(policy, changed_paths):
    """Paths whose document fields the product derives: explicit policy paths and changed files matching a schema glob."""
    from drift_gate.utils.glob_matcher import matches_any
    # Glob groups inspect only already collected changed documents. No
    # unbounded repository traversal or remote listing is implied.
    paths = {path for rule in policy.rules for group in rule.require.groups
             if group.content in ENV_DOCUMENT_CONTENT
             for path in (group.any_changed or group.all_changed) if not any(c in path for c in '*?[]')}
    schema = list(schema_document_paths(policy))
    paths.update(path for path in changed_paths if matches_any(path, schema))
    return paths


def document_fields(path, text, schema_paths):
    """Derived document fields for text the caller already read; None means the document is missing."""
    from drift_gate.utils.glob_matcher import matches_any
    normalized, error = None, ''
    try:
        state = "available" if text is not None else "missing"
        keys = sorted(env_keys_in_document(text)) if text is not None else []
        if text is not None and matches_any(path, list(schema_paths)) and path.lower().endswith(('.yaml', '.yml')):
            normalized = normalize_openapi_yaml(text)
    except (OSError, ValueError, RuntimeError):
        keys, state, error = None, "unavailable", UNAVAILABLE_ERROR
    return {"documented_env_keys": keys, "document_input_state": state,
            "document_json": normalized, "document_error": error}


def attach_env_documents(files, policy, read_text):
    schema_paths = schema_document_paths(policy)
    by_path = {file.path: file for file in files}
    for path in sorted(document_paths(policy, [file.path for file in files])):
        file = by_path.get(path, ChangedFile.from_source(ChangedFileSource(path=path, status="unchanged")))
        try:
            text = None if file.status == "deleted" else read_text(path)
        except (OSError, ValueError, RuntimeError):
            text = None
            fields = {"documented_env_keys": None, "document_input_state": "unavailable",
                      "document_json": None, "document_error": UNAVAILABLE_ERROR}
        else:
            fields = document_fields(path, text, schema_paths)
        by_path[path] = replace(file, after_source=text, **fields)
    return list(by_path.values())


def local_document_reader(root):
    root = Path(root).resolve()

    def read(path):
        if (root / path).is_symlink():
            raise ValueError("symlink documents are not supported")
        target = (root / path).resolve()
        if not target.is_relative_to(root):
            raise ValueError("document is outside the repository")
        if not target.exists():
            return None
        return read_bounded_text(target)
    return read
