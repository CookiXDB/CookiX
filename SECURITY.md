# Security

CookiX is a database engine with two interfaces: the embedded Python library
(trusted, in-process) and an optional HTTP server (`cookix serve`). This document
states the threat model honestly — what is protected, what is not, and the known
limitations — rather than implying a guarantee the code does not provide.

## Reporting a vulnerability

Please report security issues privately to the maintainer rather than opening a
public issue. We aim to acknowledge within a few days.

## Threat model

The HTTP server is designed for **single-node, trusted-network or
authenticated** deployment. It is not (yet) a hardened public-internet,
multi-tenant service.

### What the server protects against (opt-in via `ServerConfig` / `COOKIX_*` env)

- **Unauthenticated access** — set `COOKIX_API_KEY` (or `--api-key`) to require
  `Authorization: Bearer <key>` / `X-API-Key` on all data endpoints. The key is
  compared in constant time (`hmac.compare_digest`).
- **Over-privileged keys** — `COOKIX_API_KEYS="k1:read,k2:write,k3:admin"` issues
  role-scoped keys: read endpoints need `read`, mutations need `write`. A
  read-only key cannot write (`403`).
- **Accidental public exposure** — `serve` refuses to bind a non-loopback
  interface without auth unless you explicitly pass `--insecure` /
  `COOKIX_ALLOW_INSECURE=1`. (The demo Docker image sets this flag on purpose;
  set an API key for any real deployment.)
- **Request floods** — `COOKIX_RATE_LIMIT_RPM` enables a per-client fixed-window
  rate limiter returning `429`.
- **Resource-exhausting queries** — `k` and `max_hops` are clamped to configured
  ceilings, so one request cannot ask the engine for unbounded work.
- **Oversized payloads** — requests above `COOKIX_MAX_BODY_BYTES` are rejected
  with `413`.
- **Unwanted writes** — `COOKIX_READ_ONLY` rejects all mutations with `403`.
- **CORS** — none is configured, so browsers block cross-origin calls by default.

### Known limitations (be explicit)

- **Defaults are open.** With no config, the server has no auth and no rate
  limit — convenient for the demo UI, unsafe to expose directly. Always set an
  API key and a rate limit (or front it with a reverse proxy) for any networked
  deployment.
- **Body-size check uses `Content-Length`.** A chunked request without that
  header bypasses the middleware cap; set a body limit at your reverse
  proxy/ingress as defence in depth.
- **Rate limiting is per-process and in-memory.** It does not coordinate across
  replicas; multi-node rate limiting is out of scope for the single-node v1.0.
- **`/metrics` and `/api/info` are unauthenticated** (object counts, version,
  relation vocabulary). Disable metrics with `COOKIX_METRICS=0` if that matters,
  or restrict them at the proxy.
- **On-disk format uses `pickle`.** Snapshots and the write-ahead log are local,
  trusted files written by CookiX itself — never a deserialization surface for
  external input. Do not load a snapshot/WAL from an untrusted source.

## Data handling

CookiX stores exactly the Knowledge Objects you insert. It does not phone home,
collect telemetry, or transmit data anywhere. The optional LLM extractor
(`cookix[llm]`) sends text you pass it to the Anthropic API using your own key.
