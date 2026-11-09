# Resume bullet template

Only technical facts are stated without brackets. Any outcome, percentage, time saving or scale
claim that would be **measured** is left as a placeholder so it cannot be invented.

## Core bullets

- Built a reproducible synthetic wealth-management analytics workbench with Python, SQL,
  DuckDB and Streamlit, covering `[N]` clients and `[M]` transactions from a seeded generator.
- Modelled a normalised operational schema and star-schema marts with SCD2 advisor assignments
  and as-of joins; validated the warehouse with `[N]` automated data-quality checks.
- Defined and tested `[N]` KPI views covering NNA, fee-based asset share, channel mix, digital
  migration, cohort retention, advisor productivity and client segments, with documented grain,
  units and caveats.
- Built a six-page Streamlit dashboard with date/channel/segment filters, advisor drill-down,
  metric definitions and a data-quality workspace.
- Implemented a guarded NL-to-SQL layer over allow-listed, read-only analytics views, blocking
  `[N]` adversarial statement classes and retaining an offline deterministic fallback.
- Automated the end-to-end workflow (generate → load → transform → quality → export) with a
  CLI and Make targets; reduced rebuild time to `[measured time]` on a 2-core laptop.

## Optional impact bullets (measure first)

- Reduced time to answer recurring KPI questions from `[before]` to `[after]` in a
  `[user/test]` setting.
- Cut manual reconciliation effort by `[measured amount]` by adding `[N]` automated checks.
- Improved `[metric]` from `[before]` to `[after]`, measured over `[period]` using
  `[method/tool]`.

## Do not write

- “Drove ₹X Cr of AUM” — the data is synthetic.
- “Improved retention by X%” — retention is a scenario assumption.
- “Increased advice conversion” — migration is a plan-created proxy, not causality.
- Any firm name, client name or implied affiliation.
- Any percentage you did not measure in a real setting.

## Short version

> Built a synthetic wealth-management analytics workbench (Python, SQL, DuckDB, Streamlit) with
> SCD2 attribution, `[N]` tested KPI views, `[N]` data-quality checks, a six-page dashboard and a
> guarded read-only NL-to-SQL demo.
