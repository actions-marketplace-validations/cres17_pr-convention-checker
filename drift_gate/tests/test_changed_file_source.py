import dataclasses

import pytest

from drift_gate.core.models import ChangedFile, ChangedFileSource
from drift_gate.core.models.changed_file import FACT_FIELDS, SOURCE_FIELDS


# Pins the order that snapshots and input digests serialize today.
SERIALIZED_ORDER = [
    "path", "status", "previous_path", "patch",
    "semantic_signals", "semantic_evidence", "analysis_method", "analysis_reason",
    "documented_env_keys", "document_input_state",
    "before_source", "after_source", "document_json", "document_error",
    "before_routes", "after_routes", "route_analysis_error",
    "env_key_usage", "removed_env_key_candidates",
]


def test_source_and_fact_fields_partition_every_changed_file_field():
    fact_names = [name for group in FACT_FIELDS.values() for name in group]
    all_names = list(SOURCE_FIELDS) + fact_names

    assert len(all_names) == len(set(all_names))
    assert set(all_names) == {f.name for f in dataclasses.fields(ChangedFile)}


def test_serialized_field_order_is_unchanged():
    assert list(dataclasses.asdict(ChangedFile(path="a.py", status="modified")).keys()) == SERIALIZED_ORDER


def test_source_round_trip_keeps_facts_at_defaults():
    source = ChangedFileSource(
        path="src/app.py",
        status="renamed",
        previous_path="src/old.py",
        patch="@@ -1 +1 @@",
        before_source="a = 1\n",
        after_source="a = 2\n",
    )

    changed = ChangedFile.from_source(source)

    assert changed.source == source
    assert changed.analysis_method == "not-analyzed"
    assert changed.semantic_signals == []
    assert changed.before_routes is None
    assert changed.documented_env_keys is None


def test_from_source_rejects_plain_dicts_and_changed_files():
    with pytest.raises(TypeError):
        ChangedFile.from_source({"path": "a.py", "status": "added"})
    with pytest.raises(TypeError):
        ChangedFile.from_source(ChangedFile(path="a.py", status="added"))


def test_changed_file_source_is_frozen():
    source = ChangedFileSource(path="a.py", status="added")

    with pytest.raises(dataclasses.FrozenInstanceError):
        source.path = "b.py"
