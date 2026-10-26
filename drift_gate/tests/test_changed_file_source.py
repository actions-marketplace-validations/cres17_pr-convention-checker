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


def test_from_dict_accepts_source_fields_only():
    changed = ChangedFile.from_dict({"path": "a.py", "before_source": "x = 1\n", "after_source": "x = 2\n"})

    assert changed.source == ChangedFileSource(path="a.py", status="modified",
                                               before_source="x = 1\n", after_source="x = 2\n")


@pytest.mark.parametrize("key", ["semantic_signals", "document_input_state", "env_key_usage"])
def test_from_dict_rejects_derived_fields(key):
    with pytest.raises(ValueError, match="derived fields"):
        ChangedFile.from_dict({"path": "a.py", "status": "modified", key: None})


def test_from_dict_rejects_unknown_fields():
    with pytest.raises(ValueError, match="unknown changed-file fields"):
        ChangedFile.from_dict({"path": "a.py", "note": "x"})


def test_legacy_fixture_keeps_recorded_facts():
    changed = ChangedFile.from_legacy_fixture({
        "path": "docs/env.md", "status": "unchanged", "documented_env_keys": ["API_KEY"],
        "document_input_state": "available",
    })

    assert changed.documented_env_keys == ["API_KEY"]
    assert changed.document_input_state == "available"
    assert list(dataclasses.asdict(changed).keys()) == SERIALIZED_ORDER


@pytest.mark.parametrize("key", ["analysis_method", "env_key_usage", "removed_env_key_candidates"])
def test_legacy_fixture_rejects_facts_outside_its_allowlist(key):
    with pytest.raises(ValueError, match="unknown changed-file fields"):
        ChangedFile.from_legacy_fixture({"path": "a.py", "status": "modified", key: None})


def test_changed_file_source_is_frozen():
    source = ChangedFileSource(path="a.py", status="added")

    with pytest.raises(dataclasses.FrozenInstanceError):
        source.path = "b.py"
