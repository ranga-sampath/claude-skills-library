# Overview: iptables-diff-explain — Claude Code Skill

## What This Skill Is

An **operational Claude Code skill** — invoked via `/iptables-diff-explain` — that compares two `iptables-save` snapshots (before and after a change) and produces a plain-English explanation of what changed, why it matters, and what the security impact is. Analysis runs natively inside Claude Code; no external API key is required.

## The Problem It Solves

When a change window closes, a hardening script runs, or Docker starts on a host, the iptables ruleset may change significantly. Understanding exactly what changed — which chains were added, which rules were removed, whether the posture tightened or loosened, and what services might now be broken — requires diffing two complex multi-table rulesets and interpreting the delta.

This skill does that diff and interpretation automatically, producing a human-readable change explanation that is ready for a change review or incident postmortem.

## Architecture: Four Stages

```
before.txt (iptables-save)     after.txt (iptables-save)
    │                               │
    ▼                               ▼
[Stage 2a] Parse              [Stage 2b] Parse
    │  iptables_parser.py          │  iptables_parser.py
    │  → structured JSON           │  → structured JSON
    └──────────┬───────────────────┘
               ▼
[Stage 3] Diff  (iptables_diff.py)
    │  Compare two structured JSONs
    │  Detect: policy changes, chains added/removed,
    │           rules added/removed/repositioned
    │  Set: drift_detected, has_critical_changes
    ▼
[Stage 4] AI Analysis  (Claude Code — native)
       Reads diff JSON
       Applies expert change analysis framework
       Returns: Change Summary, Policy Changes, Rules Added/Removed,
                Chains Added/Removed, Overall Assessment, Recommended Actions
```

**Stages 1–3** run in `iptables_parser.py` + `iptables_diff.py` (Python stdlib only).

**Stage 4** runs natively inside Claude Code — no separate API call or API key.

## What the Differ Produces

The differ compares two structured parser outputs and produces a diff JSON containing:

- **`drift_detected`** — `true` if any change was found
- **`has_critical_changes`** — `true` if a DROP/REJECT policy change, new DROP rule, or chain removal was detected
- **`summary`** — counts: tables added/removed, chains added/removed, policy changes, rules added/removed/repositioned
- **`changes`** — full detail:
  - `policy_changes` — chain-level default policy before/after
  - `chains_added` / `chains_removed` — with full rule contents of each chain
  - `rules_added` / `rules_removed` — full rule objects
  - `rules_repositioned` — rule moved to a different position within its chain

Critically, `chains_added` and `chains_removed` include the **full rule list** of each chain — so when Docker starts and adds DOCKER-FORWARD with a DROP rule, Claude sees the rule content, not just the chain name.

## Change Detection Logic

| Change Type | Detection Method |
|---|---|
| Policy change | Chain default_policy before ≠ after |
| Chain added | Chain present in after, absent in before |
| Chain removed | Chain present in before, absent in after |
| Rule added | Rule `raw_rule` present in after chain, absent in before |
| Rule removed | Rule `raw_rule` present in before chain, absent in after |
| Rule repositioned | Same `raw_rule` in both, but at different position |
| Table added/removed | Table key present in one snapshot only |

Rules are matched by normalised `raw_rule` string. Position changes of identical rules are recorded separately as repositioning events.

## `has_critical_changes` Flag

The differ marks a change as critical if any of the following are true:
- A base chain (INPUT, FORWARD, OUTPUT) policy changes to DROP
- A DROP or REJECT rule is added to INPUT or FORWARD
- A chain with DROP rules is added to the call graph of INPUT or FORWARD
- Any chain is removed (potential loss of protection)

This allows Claude to prioritise its analysis — critical changes are always led first.

## Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Rule matching | By normalised raw_rule string | Position-independent; handles reordering correctly |
| Chain contents in diff | Full rule list included | LLM sees DROP rules inside added chains; prevents misdiagnosis |
| Two-step (parse then diff) | Yes | Parser is reusable standalone; diff is composable |
| Temporary files | `/tmp/iptables_$$.json` | Isolated per invocation; cleaned up after diff |

## What This Skill Intentionally Omits

| Omitted | Why |
|---|---|
| Semantic diff of rule content | Rules are added/removed atomically; in-place edits are remove+add |
| IPv6 auto-diff | ip6tables-save is a separate file |
| Historical diff tracking | Each invocation is a one-time before/after comparison |
