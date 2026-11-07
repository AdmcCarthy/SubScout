# Tables

Tables are the **precise layer**: prose rounds, charts show the pattern, tables give the exact
numbers. Use one when the reader needs to look up or compare individual values, when precision
matters, or when several units sit side by side (Few).

## Craft defaults (Schwabish, *Ten Guidelines for Better Tables*, 2020)

1. Header set apart from the body.
2. Subtle dividers, not gridlines.
3. Numbers right-aligned, with tabular figures.
4. Text left-aligned.
5. Precision suited to each column.
6. Spacing that guides the eye along rows.
7. Units once, in the header.
8. Outliers highlighted.
9. Related rows grouped.
10. Small charts where they help.

Readers read row by row and give up on long tables (Datawrapper): fold long tables, and prefer a
sparkline to showing only first and last values.

## Five kinds

| `kind:` | Job | Design |
|---|---|---|
| `league` | Ranking | Sorted; rank column; inline bar; story rows highlighted; `fold:` the rest behind "Show all" |
| `heat` | Scorecard | Cells shaded by sequential or diverging tokens; text flips light/dark to keep contrast |
| `trend` | Change over time | Sparkline per row (end dot, min/max), latest value, change |
| `range` | Uncertainty | P90 / P50 / P10 columns and an inline range bar; "P90 (low)" labelled |
| `ledger` | Traceability | Value, calculation, source, confidence: used by the appendix numbers ledger |

## Tables in the narrative

- **States, like charts:** highlight a row, re-sort (rows slide, keeping object constancy), reveal a
  column, in both Read and Present.
- **Action title and margin notes** point at the rows that matter.
- **Morph** (Outcrop): inline bars grow into a full bar chart, or the reverse.
- The units toggle, traceability and confidence apply as for charts.
- **Phones:** priority columns, sticky first column, card layout below 600px.
- Always a real `<table>` with a caption and `aria-sort`.
