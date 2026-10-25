import ast
from pathlib import Path

from drift_gate.core.models.changed_file import FACT_FIELDS

PACKAGE = Path(__file__).resolve().parents[1]
FACTS = {name for group in FACT_FIELDS.values() for name in group}

# Only the analysis modules may fill derived fields by keyword.
# changed_file.py is listed until from_dict stops accepting derived fields.
ALLOWED = {
    "adapters/ast/analyzer.py",
    "adapters/ast/express_routes.py",
    "adapters/docs/content.py",
    "adapters/removed_key_usage.py",
    "core/evaluation/evaluator.py",
    "core/models/changed_file.py",
}


def _writes_facts(source):
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
        if name in {"ChangedFile", "replace"} and any(kw.arg in FACTS for kw in node.keywords):
            return True
    return False


def _product_writers():
    found = set()
    for path in PACKAGE.rglob("*.py"):
        rel = path.relative_to(PACKAGE).as_posix()
        if rel.startswith("tests/"):
            continue
        if _writes_facts(path.read_text(encoding="utf-8")):
            found.add(rel)
    return found


def test_only_analysis_modules_write_derived_fields():
    assert _product_writers() <= ALLOWED


def test_detector_flags_direct_derived_field_writes():
    assert _writes_facts("ChangedFile(path='a', status='added', semantic_signals=[])")
    assert _writes_facts("replace(file, document_error='x')")
    assert not _writes_facts("ChangedFile.from_source(ChangedFileSource(path='a', status='added'))")
