"""Before/after dependency graphs and impact scope (design W11).

Edges are static imports (Python ``import``/``from``, JS/TS ``import``/
``require`` with literal specifiers) between repository modules. Anything the
profile cannot resolve statically is an open boundary, never a missing edge:
dynamic imports, unresolved relative imports and unresolved imports of a
top-level package that exists in the repository. Imports of packages outside the
repository are listed as external boundaries under an explicit assumption that
they contribute no repository contract facts.

``affected`` is reverse reachability from the seeds in Gbefore ∪ Gafter, so a
consumer that lost its edge in the head is still affected. ``analysis_scope``
adds the forward dependencies those modules need for registration and models.
"""
import ast
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

PY = ('.py',)
JS = ('.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs')
_JS_IMPORT = re.compile(r'''(?:^|[^.\w$])(?:import\s+(?:[^'"]*?\s+from\s+)?|export\s+[^'"]*?\s+from\s+)(['"])([^'"\n]+)\1''')
_JS_REQUIRE = re.compile(r'''(?:^|[^.\w$])require\s*\(\s*(['"])([^'"\n]+)\1\s*\)''')
# ``import("./x")`` with a literal specifier is resolved like a static import (review 791565f R6).
_JS_LITERAL_IMPORT = re.compile(r'''(?:^|[^.\w$])import\s*\(\s*(['"])([^'"\n]+)\1\s*\)''')
# The whitespace sits inside the lookahead: a leading ``\s*`` could backtrack and flag a literal call.
_JS_DYNAMIC = re.compile(r'''(?:^|[^.\w$])(?:require|import)\s*\((?!\s*['"][^'"\n]*['"]\s*\))''')


@dataclass(frozen=True)
class Boundary:
    module: str
    kind: str      # dynamic-import | unresolved-relative | unresolved-internal | parse-error | external | limit
    detail: str

    def to_dict(self):
        return {'module': self.module, 'kind': self.kind, 'detail': self.detail}


OPEN_KINDS = ('dynamic-import', 'unresolved-relative', 'unresolved-internal', 'parse-error', 'limit')


@dataclass(frozen=True)
class Graph:
    modules: frozenset
    edges: frozenset            # (importer, imported)
    boundaries: tuple = field(default=())

    @property
    def open_boundaries(self):
        return tuple(b for b in self.boundaries if b.kind in OPEN_KINDS)


def _python_module_index(paths):
    index = {}
    for path in paths:
        if not path.endswith('.py'):
            continue
        parts = PurePosixPath(path).with_suffix('').parts
        if parts[-1] == '__init__':
            parts = parts[:-1]
        if parts:
            index.setdefault('.'.join(parts), path)
            # src-layout: "src/pkg/mod.py" is importable as "pkg.mod".
            if parts[0] in {'src', 'lib'} and len(parts) > 1:
                index.setdefault('.'.join(parts[1:]), path)
    return index


def _longest(name, index):
    parts = name.split('.')
    for end in range(len(parts), 0, -1):
        candidate = '.'.join(parts[:end])
        if candidate in index:
            return index[candidate]
    return None


def _python_edges(path, text, index, top_level):
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return set(), [Boundary(path, 'parse-error', 'python source could not be parsed')]
    edges, boundaries = set(), []
    package = PurePosixPath(path).parent.parts

    def absolute(name):
        target = _longest(name, index)
        if target:
            edges.add(target)
        elif name.split('.')[0] in top_level:
            boundaries.append(Boundary(path, 'unresolved-internal', name))
        else:
            boundaries.append(Boundary(path, 'external', name.split('.')[0]))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                absolute(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                if node.level - 1 > len(package):
                    boundaries.append(Boundary(path, 'unresolved-relative', f'level {node.level} beyond root'))
                    continue
                base = package[:len(package) - (node.level - 1)]
                module = '.'.join((*base, *(node.module.split('.') if node.module else ())))
            else:
                module = node.module or ''
            for alias in node.names:
                submodule = f'{module}.{alias.name}' if module else alias.name
                if submodule in index:
                    edges.add(index[submodule])
                elif module and module in index:
                    edges.add(index[module])
                elif node.level:
                    boundaries.append(Boundary(path, 'unresolved-relative', submodule))
                else:
                    absolute(module)
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ''
            if name in {'import_module', '__import__'}:
                literal = (node.args and isinstance(node.args[0], ast.Constant)
                           and isinstance(node.args[0].value, str) and not node.args[0].value.startswith('.'))
                if literal and _longest(node.args[0].value, index):
                    edges.add(_longest(node.args[0].value, index))
                elif literal and node.args[0].value.split('.')[0] not in top_level:
                    boundaries.append(Boundary(path, 'external', node.args[0].value.split('.')[0]))
                else:
                    boundaries.append(Boundary(path, 'dynamic-import', name))
    edges.discard(path)
    return edges, boundaries


def _js_resolve(path, specifier, paths):
    if not specifier.startswith('.'):
        return None
    base = PurePosixPath(path).parent
    target = PurePosixPath(*[part for part in (base / specifier).parts])
    normalized = []
    for part in target.parts:
        if part == '..':
            if not normalized:
                return None
            normalized.pop()
        elif part != '.':
            normalized.append(part)
    stem = '/'.join(normalized)
    for candidate in [stem] + [stem + suffix for suffix in JS] + [f'{stem}/index{suffix}' for suffix in JS]:
        if candidate in paths:
            return candidate
    return None


_SPECIFIER_CONTEXT = re.compile(r'(?:(?<![.\w$])(?:from|import)|(?<![.\w$])(?:require|import)\s*\()\s*$')
_REGEX_PRECEDER = set('(,=:[!&|?{};+-*%<>~^')
_REGEX_KEYWORDS = ('return', 'typeof', 'case', 'do', 'else', 'in', 'of', 'void', 'yield', 'await', 'delete')


def _regex_allowed(out):
    """A ``/`` starts a regular expression literal when no operand precedes it."""
    head = ''.join(out[-40:]).rstrip()
    if not head:
        return True
    if head[-1] in _REGEX_PRECEDER:
        return True
    return any(head.endswith(word) and (len(head) == len(word) or not (head[-len(word) - 1].isalnum()
                                                                         or head[-len(word) - 1] in '_$'))
               for word in _REGEX_KEYWORDS)


def _js_code_view(text):
    """Return ``text`` with comments blanked and non-specifier literal contents masked.

    Positions and line breaks are preserved. String literals keep their content only
    where a module specifier is expected (after ``from``, ``import``, ``require(`` or
    ``import(``), so import-like text inside comments, ordinary strings, template text
    and regular expression literals no longer produces edges or dynamic-import
    boundaries. Code inside template substitutions (``${...}``) is scanned as code.
    """
    out, i, n = [], 0, len(text)
    braces = []  # per open template substitution: depth of ``{`` opened inside it

    def blank(chunk):
        out.append(''.join('\n' if ch == '\n' else ' ' for ch in chunk))

    def template(start):
        """Mask template text from ``start`` until the closing backtick or a ``${``."""
        j = start
        while j < n:
            ch = text[j]
            if ch == '\\':
                j += 2
                continue
            if ch == '`':
                blank(text[start:j])
                out.append('`')
                return j + 1, False
            if ch == '$' and j + 1 < n and text[j + 1] == '{':
                blank(text[start:j])
                out.append('${')
                return j + 2, True
            j += 1
        blank(text[start:])
        return n, False

    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ''
        if ch == '/' and nxt == '/':
            end = text.find('\n', i)
            end = n if end < 0 else end
            blank(text[i:end])
            i = end
        elif ch == '/' and nxt == '*':
            end = text.find('*/', i + 2)
            end = n if end < 0 else end + 2
            blank(text[i:end])
            i = end
        elif ch in '\'"':
            j = i + 1
            while j < n and text[j] != ch and text[j] != '\n':
                j += 2 if text[j] == '\\' else 1
            body = text[i + 1:min(j, n)]
            keep = _SPECIFIER_CONTEXT.search(''.join(out[-80:])) is not None
            out.append(ch)
            out.append(body if keep else 'x' * len(body))
            if j < n and text[j] == ch:
                out.append(ch)
                j += 1
            i = j
        elif ch == '`':
            out.append('`')
            i, opened = template(i + 1)
            if opened:
                braces.append(0)
        elif ch == '/' and _regex_allowed(out):
            j, in_class = i + 1, False
            while j < n and text[j] != '\n':
                if text[j] == '\\':
                    j += 2
                    continue
                if text[j] == '[':
                    in_class = True
                elif text[j] == ']':
                    in_class = False
                elif text[j] == '/' and not in_class:
                    break
                j += 1
            if j < n and text[j] == '/':
                out.append('/' + 'x' * (j - i - 1) + '/')
                i = j + 1
            else:  # not a closed literal on this line: treat as an operator
                out.append(ch)
                i += 1
        elif braces and ch == '{':
            braces[-1] += 1
            out.append(ch)
            i += 1
        elif braces and ch == '}':
            if braces[-1]:
                braces[-1] -= 1
                out.append(ch)
                i += 1
            else:
                braces.pop()
                out.append('}')
                i, opened = template(i + 1)
                if opened:
                    braces.append(0)
        else:
            out.append(ch)
            i += 1
    return ''.join(out)


def _js_edges(path, text, paths):
    edges, boundaries = set(), []
    text = _js_code_view(text)
    for pattern in (_JS_IMPORT, _JS_REQUIRE, _JS_LITERAL_IMPORT):
        for match in pattern.finditer(text):
            specifier = match.group(2)
            if specifier.startswith('.'):
                target = _js_resolve(path, specifier, paths)
                if target:
                    edges.add(target)
                else:
                    boundaries.append(Boundary(path, 'unresolved-relative', specifier))
            else:
                boundaries.append(Boundary(path, 'external', specifier.split('/')[0]))
    if _JS_DYNAMIC.search(text):
        boundaries.append(Boundary(path, 'dynamic-import', 'non-literal require/import'))
    edges.discard(path)
    return edges, boundaries


def build_graph(sources, *, max_edges=200_000):
    """``sources``: {path: text or None}. None means the module could not be read (open)."""
    paths = frozenset(sources)
    index = _python_module_index(paths)
    top_level = {name.split('.')[0] for name in index}
    edges, boundaries = set(), []
    for path in sorted(paths):
        text = sources[path]
        if text is None:
            boundaries.append(Boundary(path, 'parse-error', 'source unavailable'))
            continue
        if path.endswith(PY):
            found, open_ = _python_edges(path, text, index, top_level)
        elif path.endswith(JS):
            found, open_ = _js_edges(path, text, paths)
        else:
            continue
        edges.update((path, target) for target in found)
        boundaries.extend(open_)
        if len(edges) > max_edges:
            boundaries.append(Boundary(path, 'limit', f'edge limit {max_edges} reached'))
            break
    unique = tuple(sorted(set(boundaries), key=lambda b: (b.module, b.kind, b.detail)))
    return Graph(paths, frozenset(edges), unique)


def strongly_connected(graph):
    """Iterative Tarjan; returns cycles (SCCs with more than one module or a self edge)."""
    adjacency = {}
    for source, target in graph.edges:
        adjacency.setdefault(source, []).append(target)
    index, low, stack, on_stack, result, counter = {}, {}, [], set(), [], [0]
    for start in sorted(graph.modules):
        if start in index:
            continue
        work = [(start, iter(sorted(adjacency.get(start, ()))))]
        index[start] = low[start] = counter[0]; counter[0] += 1
        stack.append(start); on_stack.add(start)
        while work:
            node, children = work[-1]
            advanced = False
            for child in children:
                if child not in index:
                    index[child] = low[child] = counter[0]; counter[0] += 1
                    stack.append(child); on_stack.add(child)
                    work.append((child, iter(sorted(adjacency.get(child, ())))))
                    advanced = True
                    break
                if child in on_stack:
                    low[node] = min(low[node], index[child])
            if advanced:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[node])
            if low[node] == index[node]:
                component = []
                while True:
                    member = stack.pop(); on_stack.discard(member); component.append(member)
                    if member == node:
                        break
                if len(component) > 1:
                    result.append(tuple(sorted(component)))
    return sorted(result)


def _reach(starts, adjacency):
    seen, frontier = set(starts), list(starts)
    while frontier:
        node = frontier.pop()
        for nxt in adjacency.get(node, ()):
            if nxt not in seen:
                seen.add(nxt); frontier.append(nxt)
    return seen


@dataclass(frozen=True)
class ImpactScope:
    seeds: tuple
    affected: tuple
    analysis_scope: tuple
    removed_edges: tuple
    added_edges: tuple
    cycles: tuple
    open_boundaries: tuple
    external_boundaries: tuple

    @property
    def closed(self):
        return not self.open_boundaries

    def boundaries_for(self, modules):
        modules = set(modules)
        return tuple(b for b in self.open_boundaries if b.module in modules)

    def to_dict(self):
        return {'schema': 'dependency-impact-v1', 'seeds': list(self.seeds), 'affected': list(self.affected),
                'analysis_scope': list(self.analysis_scope),
                'removed_edges': [list(edge) for edge in self.removed_edges],
                'added_edges': [list(edge) for edge in self.added_edges],
                'cycles': [list(cycle) for cycle in self.cycles],
                'closed': self.closed, 'open_boundaries': [b.to_dict() for b in self.open_boundaries],
                'external_boundaries': sorted({b.detail for b in self.external_boundaries}),
                'assumptions': ['external-packages-contribute-no-repository-contract-facts',
                                'static-literal-imports-only']}


def impact(before, after, seeds):
    if not isinstance(before, Graph) or not isinstance(after, Graph):
        raise ValueError('impact requires two graphs')
    seeds = tuple(sorted(set(seeds)))
    union = before.edges | after.edges
    reverse, forward = {}, {}
    for source, target in union:
        reverse.setdefault(target, set()).add(source)
        forward.setdefault(source, set()).add(target)
    affected = _reach(seeds, reverse)
    scope = _reach(affected, forward)
    union_graph = Graph(before.modules | after.modules, frozenset(union))
    boundaries = tuple(sorted(set(before.boundaries) | set(after.boundaries),
                              key=lambda b: (b.module, b.kind, b.detail)))
    # Any open boundary can hide an edge: inside the scope it may reach more modules, outside it a module
    # with an unresolved import may depend on a seed and belong to ``affected``. Either way not closed.
    relevant_open = tuple(b for b in boundaries if b.kind in OPEN_KINDS)
    external = tuple(b for b in boundaries if b.kind == 'external' and b.module in scope)
    return ImpactScope(seeds, tuple(sorted(affected)), tuple(sorted(scope)),
                       tuple(sorted(before.edges - after.edges)), tuple(sorted(after.edges - before.edges)),
                       tuple(strongly_connected(union_graph)), relevant_open, external)
