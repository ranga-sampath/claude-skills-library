# Overview: nftables-diff-explain — Claude Code Skill

## What This Skill Is

An **operational Claude Code skill** — invoked via `/nftables-diff-explain` — that compares two `nft --json list ruleset` snapshots (before and after a change) and produces a plain-English explanation of what changed, why it matters, and what the security impact is. Analysis runs natively inside Claude Code; no external API key is required.

## The Problem It Solves

nftables change management is hard. A single change window may add or remove tables, chains, rules, and named sets across multiple address families. Policy changes on base chains (input, forward) have immediate and broad effect. Rule deletions may silently remove active bans or protection layers. The `nft --json list ruleset` format captures the complete state at a point in time, but diffing two such snapshots manually is tedious and error-prone.

This skill automates the diff and produces a structured, prioritised change explanation that can be used for change review, incident postmortem, or compliance evidence.

## Architecture: Four Stages

```
before.json (nft --json list ruleset)    after.json (nft --json list ruleset)
    │                                        │
    ▼                                        ▼
[Stage 2a] Parse                      [Stage 2b] Parse
    │  nftables_parser.py                   │  nftables_parser.py
    │  → structured JSON                    │  → structured JSON
    └──────────────┬────────────────────────┘
                   ▼
[Stage 3] Diff  (nftables_diff.py)
    │  Compare two structured JSONs
    │  Detect: policy changes, tables/chains added/removed,
    │           rules added/removed/repositioned/recreated
    │  Set: drift_detected, has_critical_changes
    ▼
[Stage 4] AI Analysis  (Claude Code — native)
       Reads diff JSON
       Applies expert change analysis framework
       Returns: Change Summary, Policy Changes, Rules Added/Removed,
                Chains Added/Removed, Overall Assessment, Recommended Actions
```

**Stages 1–3** run in `nftables_parser.py` + `nftables_diff.py` (Python stdlib only).

**Stage 4** runs natively inside Claude Code — no separate API call or API key.

## What the Differ Produces

The differ compares two structured parser outputs and produces a diff JSON containing:

- **`drift_detected`** — `true` if any change was found
- **`has_critical_changes`** — `true` if a DROP policy appears on an input/forward hook, DROP rules are added, or chains/tables are removed
- **`summary`** — counts: tables, chains, policy changes, rules added/removed/repositioned/recreated
- **`changes`** — full detail:
  - `policy_changes` — base chain policy before/after
  - `tables_added` / `tables_removed` — table names
  - `chains_added` / `chains_removed` — with full rule contents
  - `rules_added` / `rules_removed` — full rule objects
  - `rules_repositioned` — rule at different position within chain
  - `rules_recreated` — same handle, different expression (in-place rule replacement)
- **`baseline_parse_warnings`** / **`current_parse_warnings`** — any structural anomalies, including handle reuse across snapshots

## Rule Identity and the `rules_recreated` Category

nftables assigns each rule a **handle** — a numeric ID that persists across `nft` operations. The differ uses handle as the primary rule identity key. When the same handle exists in both snapshots but with different content (different `expression_hash`), the rule was replaced in-place. The differ records this as a parse warning and classifies the change as remove+add.

This is distinct from iptables, where rules have no stable handle and are matched by normalised rule string.

## Parse Warnings in Diff Output

The diff JSON may include parse warnings such as:
> *"Handle N in table/chain has different expression_hash between baseline and current — possible parser bug or malformed input; recording as remove+add"*

This indicates an in-place rule replacement (same handle, new content). It is correct behaviour, not a bug. Claude's analysis section explains these in the Rules Repositioned / Rules Recreated context.

## Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Rule identity | nft handle | Stable across flush-and-reload; matches kernel's own ID |
| Chain contents in diff | Full rule objects | LLM sees DROP rules inside added chains; prevents misdiagnosis |
| `rules_recreated` category | Separate from repositioned | In-place replacement is semantically different from a position change |
| Parse warnings surfaced | Yes | Transparency; helps distinguish real changes from diff artefacts |

## What This Skill Intentionally Omits

| Omitted | Why |
|---|---|
| Named set diff | Set element changes are not yet diffed |
| Map diff | Maps are identified but element-level diff is not implemented |
| Flowtable diff | Not yet implemented |
| Historical tracking | Each invocation is a one-time before/after comparison |
