from dataclasses import dataclass


@dataclass(frozen=True)
class ChangedFileSource:
    """Raw input for one changed file, before any analysis fills derived fields."""
    path: str
    status: str  # added | modified | deleted | renamed
    previous_path: str | None = None
    patch: str = ""
    before_source: str | None = None
    after_source: str | None = None
