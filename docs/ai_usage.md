# AI usage disclosure

This project was built with an AI coding assistant (OpenCode) used for scaffolding, code
generation, SQL drafting, test ideas and documentation. The important claim is not that AI was
avoided; it is that the output is **inspectable, reproducible and tested**, and that no real or
confidential data was sent anywhere.

## 1. Where AI assisted

- Repository scaffolding, package layout and Makefile/CLI plumbing.
- Drafting the synthetic generator, SQL schema, KPI views and quality checks.
- Drafting pytest cases, including the adversarial NL-query cases.
- Drafting this documentation and the dashboard copy.
- Reviewing consistency between SQL definitions, tests and descriptions.

## 2. What was verified rather than trusted

AI output was treated as a draft, not as evidence. The following checks were run locally:

- `make demo` builds the warehouse from a clean database and completes.
- `43/43` data-quality checks pass on the default seed.
- `105` pytest tests pass, including independent re-derivations of KPI formulas.
- The dashboard is compiled and every read-only helper is exercised; the six workspaces were
  smoke-tested against the built warehouse.
- Adversarial NLQ statements are rejected by the guard.
- The synthetic data is deterministic for a fixed seed and changes for a different seed.

If a claim in the README or docs is not backed by code, a test or an explicitly labelled
assumption, it should be removed or corrected.

## 3. Runtime AI is optional

The project works fully offline. The `Ask the data` page and `wealthops nlq` command use a
deterministic keyword rules engine by default.

An optional OpenAI-compatible endpoint can be enabled with:

```bash
export WEALTHOPS_LLM_API_KEY=...
export WEALTHOPS_LLM_BASE_URL=https://api.openai.com/v1   # optional
export WEALTHOPS_LLM_MODEL=gpt-4o-mini                    # optional example
```

When enabled:

1. the question and allow-list/schema hints are sent to the configured endpoint;
2. the model is asked for one SQL statement over allow-listed views;
3. the SQL is passed through the same guard as the rules engine;
4. accepted SQL runs on a read-only DuckDB connection with an outer `LIMIT`.

The LLM is never required, and a network/configuration/parse failure falls back to the rules
engine or an error message. No API key is committed, logged or displayed.

## 4. Security controls for the NL layer

- **Allow-list:** only curated `analytics.kpi_*` / `analytics.v_*` views; raw `ops` tables are not
  readable through the assistant.
- **Statement shape:** one `SELECT` or `WITH ... SELECT`; multiple statements and comments are
  rejected.
- **Denied operations:** DML, DDL, `PRAGMA`, `ATTACH`, `DETACH`, `COPY`, `EXPORT`, `INSTALL`,
  `LOAD`, file/table functions and string-literal `FROM` targets.
- **No comma joins:** explicit `JOIN` syntax is required.
- **Qualification:** views must be written as `analytics.<view>` so execution does not depend on
  the search path.
- **Row limit:** the query is wrapped in `SELECT * FROM (<sql>) AS _guarded_query LIMIT N`, with
  N capped at 1,000 and 200 in the UI.
- **Read-only connection:** the database handle cannot write even if the guard misses something.
- **Visible SQL:** the UI shows what ran and whether it came from rules or the LLM.
- **Tests:** `tests/test_nlq.py` contains adversarial cases for DROP, DELETE, UPDATE, INSERT,
  PRAGMA, ATTACH, COPY, comments, multi-statement input, information_schema, file functions,
  raw tables, unqualified views, comma joins and string-literal targets.

The guard is intentionally conservative. It is not a general SQL parser and it may reject some
valid queries (for example certain `EXTRACT(... FROM ...)` forms). That trade-off is documented
and accepted for a demo.

## 5. Data and privacy

- No real client data, PII, firm data or confidential material was used.
- All names are generic (`Client 000001`, `Advisor 01`) and all identifiers are fabricated.
- The optional LLM sees only the user’s question, the allow-list and a short schema hint. It
  never receives the warehouse tables or client rows from this application.
- `.env` is gitignored; `.env.example` contains no secret.
- If you enable an external LLM, review that provider’s data-retention terms before sending even
  synthetic questions. The project does not send data automatically.

## 6. Limitations and risks

1. **Hallucinated SQL.** The model can invent columns or use disallowed syntax. The guard
   constrains tables/operations, but it cannot prove semantic correctness. A wrong-but-safe
   query can still return a misleading result.
2. **Rule narrowness.** The offline engine recognises curated prompts; it is not a general
   language interface.
3. **Guard conservatism.** Legitimate SQL can be rejected. This is safer than accepting
   unprovable SQL, but it is a usability cost.
4. **No semantic layer enforcement.** The allow-list controls views, not which columns or
   filters a question should use.
5. **No production tenancy.** Read-only is not row-level security. Do not expose this demo to
   untrusted users or real data without an authentication, authorisation and review layer.
6. **Documentation drift.** AI can produce plausible but stale prose. The KPI dictionary and
   tests are the intended sources of truth; update them together when a definition changes.

## 7. Evaluation stance

The project does **not** claim that the NL assistant is accurate, safe for production or better
than a human analyst. It demonstrates a governed pattern: curated views, a conservative guard,
read-only execution, visible SQL, deterministic fallback and adversarial tests. Those properties
are testable; “the model is good at SQL” is not asserted.

## 8. Suggested disclosure wording

> AI coding assistance was used to accelerate implementation and documentation. All code and
> claims were reviewed and validated with a reproducible build, 43 data-quality checks and 105
> automated tests. The application uses only synthetic data. Its optional natural-language layer
> is allow-listed, SELECT-only, row-limited and read-only; it is a demonstration of governed
> access, not a production text-to-SQL system.
