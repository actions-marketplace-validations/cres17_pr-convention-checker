from dataclasses import dataclass, field

from .changed_file_source import ChangedFileSource

SOURCE_FIELDS = (
    "path", "status", "previous_path", "patch", "before_source", "after_source",
)

# Derived fields, grouped by the analysis module that fills them.
FACT_FIELDS = {
    "semantic": ("semantic_signals", "semantic_evidence", "analysis_method", "analysis_reason"),
    "route": ("before_routes", "after_routes", "route_analysis_error"),
    "document": ("documented_env_keys", "document_input_state", "document_json", "document_error"),
    "env-usage": ("env_key_usage", "removed_env_key_candidates"),
}
_ALL_FACTS = frozenset(name for group in FACT_FIELDS.values() for name in group)
# Derived fields that frozen fixtures may record as input; from_dict rejects all others.
LEGACY_FACT_FIELDS = (
    "semantic_signals", "semantic_evidence", "documented_env_keys",
    "document_input_state", "env_key_usage", "removed_env_key_candidates",
)


def _source_of(d: dict) -> ChangedFileSource:
    return ChangedFileSource(
        path=d["path"],
        status=d.get("status", "modified"),
        previous_path=d.get("previous_path"),
        patch=d.get("patch", ""),
        before_source=d.get("before_source"),
        after_source=d.get("after_source"),
    )


@dataclass
class ChangedFile:
    path: str
    status: str  # added | modified | deleted | renamed
    previous_path: str | None = None
    patch: str = ""
    semantic_signals: list[str] = field(default_factory=list)
    semantic_evidence: list[str] = field(default_factory=list)
    analysis_method: str = "not-analyzed"
    analysis_reason: str = ""
    # Only key names are retained from document content, never values.
    documented_env_keys: list[str] | None = None
    document_input_state: str = ""  # available | missing | unavailable (adapter evidence)
    # Bounded adapter snapshots; never serialized into reports or history.
    before_source: str | None = field(default=None, repr=False)
    after_source: str | None = field(default=None, repr=False)
    # Adapter-normalized YAML; original text remains in after_source so the
    # execution receipt binds both the raw input and its normalized meaning.
    document_json: str | None = field(default=None, repr=False)
    document_error: str = ""
    before_routes: list[tuple[str, str]] | None = field(default=None, repr=False)
    after_routes: list[tuple[str, str]] | None = field(default=None, repr=False)
    route_analysis_error: str = ""
    # Captured key names, classifications and paths only; no environment values.
    env_key_usage: dict | None = field(default=None, repr=False)
    removed_env_key_candidates: list[str] | None = None

    @property
    def source(self) -> ChangedFileSource:
        return ChangedFileSource(**{name: getattr(self, name) for name in SOURCE_FIELDS})

    @classmethod
    def from_source(cls, source: ChangedFileSource) -> "ChangedFile":
        if not isinstance(source, ChangedFileSource):
            raise TypeError("from_source requires a ChangedFileSource")
        return cls(**{name: getattr(source, name) for name in SOURCE_FIELDS})

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "status": self.status,
            "previous_path": self.previous_path,
            "patch": self.patch,
            "semantic_signals": self.semantic_signals,
            "semantic_evidence": self.semantic_evidence,
            "analysis_method": self.analysis_method,
            "analysis_reason": self.analysis_reason,
            "documented_env_keys": self.documented_env_keys,
            "document_input_state": self.document_input_state,
            **({"removed_env_key_candidates": self.removed_env_key_candidates} if self.removed_env_key_candidates is not None else {}),
            **({"env_key_usage": self.env_key_usage} if self.env_key_usage is not None else {}),
            **({"document_error": self.document_error} if self.document_error else {}),
            **({"route_analysis_error": self.route_analysis_error} if self.route_analysis_error else {}),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ChangedFile":
        unknown = set(d) - set(SOURCE_FIELDS)
        if unknown & _ALL_FACTS:
            raise ValueError(f"derived fields are not accepted as input: {sorted(unknown & _ALL_FACTS)}")
        if unknown:
            raise ValueError(f"unknown changed-file fields: {sorted(unknown)}")
        return cls.from_source(_source_of(d))

    @classmethod
    def from_legacy_fixture(cls, d: dict) -> "ChangedFile":
        """Frozen fixtures that record some derived facts as input."""
        unknown = set(d) - set(SOURCE_FIELDS) - set(LEGACY_FACT_FIELDS)
        if unknown:
            raise ValueError(f"unknown changed-file fields: {sorted(unknown)}")
        changed = cls.from_source(_source_of(d))
        for name in LEGACY_FACT_FIELDS:
            if name in d:
                setattr(changed, name, d[name])
        return changed
