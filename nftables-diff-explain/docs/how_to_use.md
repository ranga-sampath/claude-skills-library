# How to Use: nftables-diff-explain Skill

## Installation

### 1. Clone the skills library

```bash
git clone https://github.com/ranga-sampath/claude-skills-library
cd claude-skills-library/nftables-diff-explain
```

### 2. Install the skill globally in Claude Code

Claude Code discovers skills from `~/.claude/skills/` — your global skills directory. Copying the files there registers the skill for every Claude Code session on this machine, regardless of which project directory you are working in.

```bash
mkdir -p ~/.claude/skills/nftables-diff-explain
cp .claude/skills/nftables-diff-explain/skill.md ~/.claude/skills/nftables-diff-explain/
cp .claude/skills/nftables-diff-explain/nftables_parser.py ~/.claude/skills/nftables-diff-explain/
cp .claude/skills/nftables-diff-explain/nftables_diff.py ~/.claude/skills/nftables-diff-explain/
```

### 3. Verify the skill is available

Open Claude Code and type `/` — `nftables-diff-explain` should appear in the autocomplete list.

---

## Capturing Snapshots for Comparison

The recommended pattern is to bracket the change:

```bash
# 1. Capture baseline BEFORE the change
nft --json list ruleset > before.json

# 2. Make your change (hardening script, package install, nft apply, etc.)

# 3. Capture the result AFTER the change
nft --json list ruleset > after.json

# 4. Invoke the skill
```

Both files must be the output of `nft --json list ruleset`. Plain-text `nft list ruleset` is not supported.

---

## Usage

```
/nftables-diff-explain <before.json> <after.json>
```

`before.json` is always the baseline (earlier state). `after.json` is always the current (later) state.

### Examples

```
# Review what a hardening script changed
/nftables-diff-explain pre-hardening.json post-hardening.json

# Understand what an nftables upgrade changed
/nftables-diff-explain before-upgrade.json after-upgrade.json

# Compare last-known-good against current state
/nftables-diff-explain last-good.json current.json

# Analyse the sample fixtures
/nftables-diff-explain examples/fx-03-inet-drop-policy.json examples/fx-12-icmp-ct.json
```

Claude will:
1. Check both files exist and both scripts are installed
2. Parse each file with `nftables_parser.py`
3. Compute the diff with `nftables_diff.py`
4. Analyse the diff JSON and return the change explanation inline

---

## What the Report Covers

| Section | Content |
|---|---|
| **Change Summary** | One-line count of what changed |
| **Policy Changes** | Default policy changes on base chains — highest priority |
| **Rules Added** | What each new rule permits or blocks |
| **Rules Removed** | What protection or access was revoked |
| **Chains Added / Removed** | Purpose of each chain with full rule contents |
| **Rules Repositioned** | Where evaluation order changes matter |
| **Overall Assessment** | Tightening or loosening verdict with blast radius |
| **Recommended Actions** | Specific steps to verify or remediate (critical changes only) |

---

## Parse Warnings in the Diff

The diff may include warnings such as:

> *"Handle N in table/chain has different expression_hash between baseline and current — recording as remove+add"*

This means the same nft rule handle exists in both snapshots but with different content — the rule was replaced in-place. The diff correctly records it as a removal of the old rule and addition of the new one. This is expected after an `nft replace rule` or a flush-and-reload.

---

## No-Change Case

If the two snapshots are identical, the report will be:

```
No changes detected between the two snapshots. The nftables ruleset is identical.
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `BEFORE_MISSING` / `AFTER_MISSING` | Check both paths; use absolute paths |
| `Error: Required scripts not found` | Re-run the install step for all three files |
| `Failed to parse` | Ensure both files are `nft --json list ruleset` output |
| `Failed to compute diff` | Check both parsed JSONs are non-empty |
| Missing set diff | Named set element changes are not yet diffed — verify set contents manually |

---

## Using the Scripts Standalone

Both scripts can be used independently of the Claude skill:

```bash
# Parse snapshots to JSON
python3 nftables_parser.py before.json > before_parsed.json
python3 nftables_parser.py after.json  > after_parsed.json

# Compute diff
python3 nftables_diff.py before_parsed.json after_parsed.json

# Pipe into jq
python3 nftables_diff.py before_parsed.json after_parsed.json | jq '.summary'
python3 nftables_diff.py before_parsed.json after_parsed.json | jq '.has_critical_changes'
python3 nftables_diff.py before_parsed.json after_parsed.json | jq '.changes.rules_added[] | {chain, verdict, protocol, dst_port}'
```

The JSON schemas are documented in `docs/overview.md`.
