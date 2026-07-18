# Launch kit

Ready-to-post copy for announcing CookiX. The tone is deliberately **honest, not
hype** — lead with what it does and where it loses. Technical audiences (HN,
r/MachineLearning) reward candor and punish overclaiming. Attach
[`assets/demo.gif`](assets/demo.gif) / [`assets/demo.mp4`](assets/demo.mp4).

> One rule: never claim "beats vector DBs" outright. The honest, defensible claim
> is **"returns the reasoning path, dominant on multi-hop given the entity, here's
> the benchmark including where it's only at parity."** That claim survives scrutiny.

---

## Hacker News (Show HN)

**Title:**
`Show HN: CookiX – a database that returns the reasoning path, not just a score`

**Body:**

I got tired of vector search answering relational questions with a blob of
"nearby" results and a cosine distance — no direction, no reason. So I built
CookiX: you model your domain as typed, directed edges, and queries come back
with the **path that proves the answer**.

Example: "which of my services does this CVE reach?" is a 3-hop question —
`checkout_api --depends_on--> fast_json --depends_on--> tinyparse --affected_by-->
CVE-2024-5001`. `checkout_api` and the CVE share no words and sit far apart in any
embedding space; the link only exists in the typed edges. CookiX returns the exact
chain. `pip install cookix`, embedded, no server.

Honest benchmark (this is the part I want feedback on): on 2WikiMultiHopQA, given
the question's head entity, typed traversal hits@10 **0.58 vs BM25's 0.39**
(+50%). End-to-end with a real lexical entity-linker it's at **parity** (0.38 vs
0.39) — because linking the right anchor is the bottleneck (~60% accuracy). An
LLM linker is the obvious next lever. I'm reporting parity, not victory, because
that's what the data shows.

What it's **not**: a vector DB replacement (use one for fuzzy semantic search), a
distributed system (single-node), or proof that the experimental topological/sheaf
layers help retrieval (they're optional and ablatable; I haven't shown they do).

Apache-2.0, solo project, built in Morocco. Repo + 30s demo + reproducible
benchmarks: https://github.com/CookiXDB/CookiX — would love feedback on the
linking approach and on use cases where the reasoning path matters.

*(Post Tue–Thu ~8–10am US Eastern. Then stay in the thread and answer every
comment for the first few hours — engagement is most of what determines ranking.)*

---

## X / Twitter (thread)

**1/** I built CookiX: a database that answers relational questions with the
*reasoning path* that proves them — not just a similarity score. `pip install
cookix`. 🧵 [attach demo.mp4]

**2/** Vector search clusters {rain, coat, umbrella} together and can't tell you
*"what prevents rain from reaching the coat?"* — that's a directed path, not
proximity. CookiX traverses typed edges and returns: umbrella —[prevents]→ rain
—[causes]→ wet_coat.

**3/** Real use: "which services does this CVE reach?" →
checkout_api → fast_json → tinyparse → CVE-2024-5001. Three hops, zero shared
words. A keyword/vector search can't connect them; typed traversal returns the
exact chain + blast radius.

**4/** Honest benchmark on 2WikiMultiHopQA: given the entity, hits@10 0.58 vs
BM25's 0.39 (+50%). End-to-end with a real entity linker it's at parity — linking
is the bottleneck. Reporting it straight, including where it's not (yet) a win.

**5/** Embedded Python, durable backend, explainable by design, Apache-2.0. Solo
project from Morocco 🇲🇦. Repo, 30s demo, reproducible evals:
https://github.com/CookiXDB/CookiX — feedback very welcome.

---

## LinkedIn (company-page first post — narrative)

> Upload `assets/demo.mp4` as native video (not a link — native gets more reach).

I spent the last stretch building CookiX — an open-source database that answers
relational questions with the reasoning path that proves them, not just a
similarity score. It's live: pip install cookix 🍪

The itch: vector search is great for "find me similar text," but it falls apart on
directed, multi-hop questions. Ask "which of my services does this CVE reach, and
through which dependency chain?" and a vector DB hands back a blob of nearby names
— no direction, no reason.

CookiX stores knowledge as typed, directed edges and answers by traversing them,
returning the exact chain:

checkout_api → fast_json → tinyparse → CVE-2024-5001

Three hops, zero shared words. That link lives only in the edges — and CookiX
shows it to you.

The honest part (I'd rather you trust the numbers than the hype): on
2WikiMultiHopQA, given the question's entity, CookiX beats BM25 by ~50% on
multi-hop retrieval — and returns the reasoning path a vector DB structurally
can't. End-to-end it's currently at parity, because linking the right entity is
the bottleneck. I'm reporting that straight; an LLM-assisted linker is next.

What it's not: a vector-DB replacement, and not (yet) distributed. It shines when
your problem is relational and you need answers you can audit — explainable RAG,
dependency/impact analysis, contraindication chains, compatibility graphs.

Apache-2.0. Built solo, in Morocco 🇲🇦. Genuinely want the hard questions.

▶️ 30-second demo + repo: github.com/CookiXDB/CookiX

\#opensource #database #AI #RAG #knowledgegraph #machinelearning

---

## Reddit (r/LocalLLaMA, r/MachineLearning, r/databases)

**Title:** `CookiX: a pip-installable database that returns the reasoning path for multi-hop queries (honest benchmark inside)`

**Body:**

Open-source (Apache-2.0) reference implementation of an idea: for *relational*
questions, retrieval should return the typed, directed **path** that justifies the
answer — something cosine similarity can't express.

- `pip install cookix`, embedded (no server), or `cookix serve` for a web explorer
  that lights up the path on a graph.
- Real demo: software supply-chain — "which services does CVE-X reach, and via
  which dependency chain?"
- Honest 2WikiMultiHopQA result: hits@10 0.58 vs BM25 0.39 given the entity;
  end-to-end at parity with a lexical linker (linking is the cap — LLM linker
  next). Full reproducible eval in-repo.
- Explicit non-goals: not a vector-DB replacement, single-node only, and the
  experimental topology/sheaf layers are *not* claimed to help retrieval yet.

Repo + 30s demo: https://github.com/CookiXDB/CookiX. I'd especially like critique
of the entity-linking approach and pointers to datasets where explainable
multi-hop retrieval matters.

---

## After you post

- **Reply to every comment** for the first few hours, especially critical ones —
  engaging well (and conceding fair points) is what builds credibility.
- If someone asks "why not Neo4j / a vector DB?", point them at the
  *when-to-reach-for-what* table in the README. Own the niche; don't fight on
  their turf.
- The strongest follow-up is the **LLM-linker benchmark number** — if it clears
  ~70% linking and flips end-to-end to a win, that's a second post ("update: it
  now beats BM25 end-to-end, here's how").
