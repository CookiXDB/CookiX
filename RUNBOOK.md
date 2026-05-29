# CookiX operations runbook

A practical on-call guide for running the CookiX server in production. Pair it
with [SECURITY.md](SECURITY.md) (threat model) and [RELEASING.md](RELEASING.md).

## Health & monitoring

| Endpoint | Meaning | Alert when |
|---|---|---|
| `GET /healthz` | process is alive | non-200 or no response → restart |
| `GET /readyz` | DB reachable (`{"status":"ready","objects":N}`) | non-200 → not ready, pull from LB |
| `GET /metrics` | Prometheus metrics (see below) | scrape every 15s |

Key metrics (`cookix_*`): `requests_total{path,status}`, `request_latency_ms_avg`,
`rate_limited_total`, `auth_failures_total`. A ready-made Grafana dashboard is in
[`ops/grafana-dashboard.json`](ops/grafana-dashboard.json).

**Suggested alerts:** p-latency or `request_latency_ms_avg` above your SLO; a
rising `5xx` rate in `requests_total`; a spike in `auth_failures_total` (probing)
or `rate_limited_total` (client misbehaving or under-provisioned limit).

## Common incidents

### Latency spike / high CPU
1. Check `requests_total` rate and `request_latency_ms_avg` on the dashboard.
2. Likely a few very wide multi-hop queries. Lower `COOKIX_MAX_HOPS` / `COOKIX_MAX_K`
   and (until fixed) the offending client's rate via `COOKIX_RATE_LIMIT_RPM`.
3. Single process is CPU-bound past ~a few hundred req/s (pure Python). Scale out
   with more `uvicorn --workers` / more replicas behind the LB.

### Memory growth
1. Confirm with the soak harness: `cookix loadtest --duration 1800 --objects 50000`
   and watch the memory columns. Flat/non-monotonic = healthy.
2. Memory scales with object count (~3 KB/object). If it tracks data growth, it's
   capacity, not a leak — add memory or shard (post-1.0).

### Crash / restart
- The `durable` backend recovers automatically on start: it loads the last
  snapshot and replays the write-ahead log. **No manual step.** Committed writes
  (those whose API call returned) survive; an in-flight write at the moment of the
  crash is simply not acknowledged.
- Verify after restart: `GET /readyz` returns the expected `objects` count.

### Suspected data corruption
1. Stop writes (deploy with `COOKIX_READ_ONLY=1`).
2. Restore the latest good backup into a fresh dir:
   `python -c "from cookix.storage.durable import DurableBackend as D; D.restore('backup.pkl','restored')"`.
3. Point the service at `restored` and resume.

### Auth failures spiking
- Probing or a rotated key. Rotate `COOKIX_API_KEY` / `COOKIX_API_KEYS`, confirm
  clients updated, and consider tightening `COOKIX_RATE_LIMIT_RPM`.

## Routine operations

- **Backup:** `DurableBackend.backup("/backups/cookix-$(date +%F).pkl")` (atomic,
  safe while serving). Schedule it; test a restore periodically.
- **Read scaling:** open one or more `DurableBackend(path, read_only=True)`
  replicas and call `refresh()` on a timer to follow the primary.
- **Upgrades:** back up first; the on-disk format refuses to load a *newer*
  version than the running build (see [API_STABILITY.md](API_STABILITY.md)).
- **Config:** all knobs are `COOKIX_*` env vars (auth, rate limit, body/`k`/hops
  caps, read-only, metrics) — no restart-unsafe state.

## What this runbook cannot give you

Real production confidence is **earned over time**, not documented. Until CookiX
has logged real uptime through real incidents (the open Phase 19 gate), treat a
new deployment as young: over-provision, alert aggressively, back up often.
