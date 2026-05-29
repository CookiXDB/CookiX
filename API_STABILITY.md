# API stability & versioning

CookiX follows [Semantic Versioning](https://semver.org/). This document states
what counts as the **public API**, what stability you can rely on, and how
changes are communicated — the promise a `1.0` is supposed to make.

## Versioned surfaces

There are three independently versioned things:

| Surface | Where | Bumped when |
|---|---|---|
| **Package version** | `cookix.__version__`, `pyproject.toml` | SemVer over the public Python API |
| **Wire-API version** | `cookix.API_VERSION`, `/api/info → api_version` | breaking change to HTTP request/response shapes |
| **On-disk format** | `cookix.storage.durable.SNAPSHOT_FORMAT_VERSION` | breaking change to the snapshot/WAL layout |

## Public Python API (covered by SemVer)

Stable — breaking changes only in a major release, with a deprecation period:

- `cookix.connect(...)` and the `Database` methods: `insert`, `insert_many`,
  `insert_text`, `get`, `delete`, `update`, `query`, `contradictions`,
  `transaction`, `save`, `__len__`, `__contains__`.
- Query modes: `"graph"`, `"topo"`, `"sheaf"`, `"reasoning"` (and their aliases).
- The `QueryResult` shape: `object_id`, `content`, `score`, `path`, `components`,
  `hops`, `explain()`.
- `KnowledgeObject` / `Edge` construction and `from_dict` / `to_dict`.
- `cookix.CookixClient` and its methods.
- Storage backend names (`"memory"`, `"durable"`, `"kuzu"`) and the
  `StorageBackend` ABC.

**Not** part of the stable API (may change at any time): anything prefixed with
`_`, the `cookix.eval.*` benchmark internals, the exact numeric scores/weights,
and the experimental topology/sheaf math internals.

## HTTP wire API

Stable endpoints and their JSON shapes are versioned by `API_VERSION` (currently
`"1"`). The server reports it at `/api/info`. Stable endpoints:

- `GET /api/info`, `GET /api/graph`, `POST /api/insert`, `POST /api/query`
- `GET /healthz`, `GET /readyz`, `GET /metrics`

A breaking change to any of these increments `API_VERSION`; additive fields are
**not** breaking, so clients must ignore unknown fields.

## On-disk format

The durable backend stamps every snapshot with `SNAPSHOT_FORMAT_VERSION`. On
open, a snapshot from a **newer** format than the running build is refused with a
clear error rather than mis-read; older formats are migrated on load (the
pre-versioning bare-dict layout is still readable). Back up before upgrading
across a major version.

## Deprecation policy

1. A deprecated API keeps working for at least one **minor** release, emitting a
   `DeprecationWarning` that names the replacement.
2. Removals happen only in a **major** release, listed in `CHANGELOG.md`.
3. Wire-API and on-disk format changes ship with a migration note.

## Release process (maintainer)

1. Update `CHANGELOG.md`; bump `__version__` and `pyproject.toml`.
2. `python -m build` → produces the wheel + sdist in `dist/`.
3. `twine check dist/*` then `twine upload dist/*` (requires PyPI credentials).
4. Tag `vX.Y.Z` and push the tag.

Publishing to PyPI requires maintainer credentials and is performed by a
maintainer; it is intentionally not automated in-repo without a trusted CI
secret.
