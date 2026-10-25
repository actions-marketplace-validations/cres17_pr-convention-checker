"""Persistent analysis cache (design W15 follow-up, 8.3).

The key binds every input that can change an analysis result: the artifact's
raw digest, the analyzer operation and profile version, the producing engine's
source digest, the reviewed parser pins, the approval context and the resource
limits. Only complete results and deterministic "unsupported" refusals are
stored. Timeouts, crashes, resource limits and other transient failures are
never cached, so a passing retry is never shadowed by an old failure. Entries
are content-addressed, written once with a no-replace link, and re-verified on
read: the stored key inputs must hash to the entry name and the stored result
must hash to the entry's ``result_sha256``. A truncated entry, or one whose
result alone was edited, is rejected and recomputed.

Trust boundary: without a key both digests sit in the same file, so anyone who
can rewrite a whole entry can forge a consistent one; the check then detects
corruption and partial edits only. With ``DRIFT_GATE_CACHE_KEY``
("key_id:base64-key", at least 32 bytes, held outside the cache directory) every
entry carries an HMAC-SHA256 over its canonical content, and entries without a
valid MAC under that key are rejected and recomputed. A writer of the cache
directory then cannot forge an entry without the key. The key is shared-secret
authentication, not a statement about who produced the entry. Cached facts stay
an optimisation; the trusted-engine path never uses a cache.
"""
import base64
import hmac
import json
import os
import re
import tempfile
from hashlib import sha256
from pathlib import Path

from drift_gate.core.models.input_manifest import canonical_bytes

SCHEMA = 'analysis-cache-entry-v2'  # v2 adds result_sha256; v1 entries are rejected and recomputed
STORABLE = ('complete', 'unsupported')
KEY_ENV = 'DRIFT_GATE_CACHE_KEY'  # "key_id:base64-key"
_KEY_ID = re.compile('[A-Za-z0-9._-]{1,64}')


class CacheError(ValueError):
    """Unusable cache configuration (never raised for a bad entry: that is a miss)."""


def cache_key_from_env(environ=None):
    """Return ``(key_id, key)`` from ``DRIFT_GATE_CACHE_KEY`` or None when unset."""
    raw = (environ if environ is not None else os.environ).get(KEY_ENV)
    if not raw:
        return None
    key_id, _, encoded = raw.partition(':')
    if not _KEY_ID.fullmatch(key_id) or not encoded:
        raise CacheError(f'{KEY_ENV} must be key_id:base64-key')
    try:
        key = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise CacheError(f'{KEY_ENV} key must be base64') from exc
    if len(key) < 32:
        raise CacheError(f'{KEY_ENV} key must be at least 32 bytes')
    return key_id, key


def _mac(key, body):
    return hmac.new(key, canonical_bytes(body), sha256).hexdigest()


def engine_digest():
    from drift_gate.adapters.evidence_bundle import producer_identity
    return producer_identity()['source_sha256']


def parser_pins_digest():
    path = Path(__file__).with_name('parser_hashes.json')
    return sha256(path.read_bytes()).hexdigest()


def key_inputs(*, artifact_sha256, op, profile, engine_sha256, parser_sha256, approvals_sha256='none',
               limits=None, scope_context='module'):
    for name, value in (('artifact_sha256', artifact_sha256), ('engine_sha256', engine_sha256),
                        ('parser_sha256', parser_sha256)):
        if not isinstance(value, str) or len(value) != 64:
            raise CacheError(f'{name} must be a SHA-256 digest')
    return {'schema': 'analysis-cache-key-v1', 'artifact_sha256': artifact_sha256, 'op': op,
            'profile': list(profile), 'engine_sha256': engine_sha256, 'parser_sha256': parser_sha256,
            'approvals_sha256': approvals_sha256, 'limits': limits or {}, 'scope_context': scope_context}


def cache_key(inputs):
    return sha256(canonical_bytes(inputs)).hexdigest()


def _result_digest(status, value):
    return sha256(canonical_bytes({'status': status, 'value': value})).hexdigest()


def _entry_ok(entry, raw, inputs, key, auth=None):
    if not (isinstance(entry, dict) and entry.get('schema') == SCHEMA and canonical_bytes(entry) == raw
            and entry.get('key_inputs') == inputs and cache_key(entry['key_inputs']) == key
            and entry.get('status') in STORABLE
            and entry.get('result_sha256') == _result_digest(entry.get('status'), entry.get('value'))):
        return False
    if auth is None:
        return True
    key_id, secret = auth
    mac = entry.get('mac')
    body = {name: value for name, value in entry.items() if name != 'mac'}
    return (isinstance(mac, dict) and mac.get('key_id') == key_id and isinstance(mac.get('hmac_sha256'), str)
            and hmac.compare_digest(mac['hmac_sha256'], _mac(secret, body)))


class AnalysisCache:
    def __init__(self, root, auth=None):
        """``auth``: ``(key_id, key)`` to require keyed entries; see :func:`cache_key_from_env`."""
        self.root = Path(root).absolute()
        self.auth = auth
        self.hits = self.misses = self.rejected = self.stored = self.skipped = 0

    def _path(self, key):
        return self.root / 'entries' / key[:2] / f'{key}.json'

    def _valid(self, path, inputs, key):
        try:
            raw = path.read_bytes()
            entry = json.loads(raw)
        except (OSError, ValueError):
            return False
        return _entry_ok(entry, raw, inputs, key, self.auth)

    def get(self, inputs):
        key = cache_key(inputs)
        path = self._path(key)
        try:
            raw = path.read_bytes()
            entry = json.loads(raw)
            valid = _entry_ok(entry, raw, inputs, key, self.auth)
        except (OSError, ValueError):
            valid = False if path.exists() else None
        if valid is None:
            self.misses += 1
            return None
        if not valid:
            self.rejected += 1  # tampered/truncated/foreign entry: recompute, never trust
            return None
        self.hits += 1
        return entry

    def put(self, inputs, *, status, value):
        """Store a complete or deterministic-unsupported result; return False when not storable."""
        if status not in STORABLE:
            self.skipped += 1
            return False
        key = cache_key(inputs)
        entry = {'schema': SCHEMA, 'key_inputs': inputs, 'status': status, 'value': value,
                 'result_sha256': _result_digest(status, value)}
        if self.auth is not None:
            entry['mac'] = {'key_id': self.auth[0], 'hmac_sha256': _mac(self.auth[1], entry)}
        raw = canonical_bytes(entry)
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor, temporary = tempfile.mkstemp(prefix='.entry-', dir=target.parent)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, target)
                self.stored += 1
            except FileExistsError:
                if not self._valid(target, inputs, key):
                    os.replace(temporary, target)  # repair a tampered/truncated entry atomically
                    self.stored += 1
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
        return True

    def stats(self):
        return {'hits': self.hits, 'misses': self.misses, 'rejected_entries': self.rejected,
                'integrity': ('keyed-hmac-rejects-entries-without-the-key' if self.auth is not None
                              else 'detects-corruption-and-partial-edits-not-forgery'),
                'stored': self.stored, 'not_stored_transient_or_incomplete': self.skipped,
                'root': str(self.root)}
