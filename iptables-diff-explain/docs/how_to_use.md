# How to Use: iptables-diff-explain Skill

## Installation

### 1. Clone the skills library

```bash
git clone https://github.com/ranga-sampath/claude-skills-library
cd claude-skills-library/iptables-diff-explain
```

### 2. Install the skill globally in Claude Code

Claude Code discovers skills from `~/.claude/skills/` — your global skills directory. Copying the files there registers the skill for every Claude Code session on this machine, regardless of which project directory you are working in.

```bash
mkdir -p ~/.claude/skills/iptables-diff-explain
cp .claude/skills/iptables-diff-explain/skill.md ~/.claude/skills/iptables-diff-explain/
cp .claude/skills/iptables-diff-explain/iptables_parser.py ~/.claude/skills/iptables-diff-explain/
cp .claude/skills/iptables-diff-explain/iptables_diff.py ~/.claude/skills/iptables-diff-explain/
```

### 3. Verify the skill is available

Open Claude Code and type `/` — `iptables-diff-explain` should appear in the autocomplete list.

---

## Capturing Snapshots for Comparison

The recommended pattern is bracket the change:

```bash
# 1. Capture baseline BEFORE the change
iptables-save > before.txt

# 2. Make your change (hardening script, package install, Docker start, etc.)

# 3. Capture the result AFTER the change
iptables-save > after.txt

# 4. Invoke the skill
```

For change-window review, both files can be captured on the same host at different times and transferred offline for analysis.

---

## Usage

```
/iptables-diff-explain <before.txt> <after.txt>
```

`before.txt` is always the baseline (earlier state). `after.txt` is always the current (later) state.

### Examples

```
# Review what a CIS hardening script changed
/iptables-diff-explain before-hardening.txt after-hardening.txt

# Understand what Docker installation added
/iptables-diff-explain pre-docker.txt post-docker.txt

# Review fail2ban adding an active ban
/iptables-diff-explain pre-ban.txt post-ban.txt

# Investigate an unexpected firewall change
/iptables-diff-explain last-known-good.txt current.txt
```

Claude will:
1. Check both files exist and both scripts are installed
2. Parse each file with `iptables_parser.py`
3. Compute the diff with `iptables_diff.py`
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

## Reading Critical Changes

The differ sets `has_critical_changes: true` when:
- A base chain policy changes to DROP
- A DROP or REJECT rule is added to INPUT or FORWARD
- A chain with DROP rules is added to the inbound path
- Any chain is removed (potential loss of protection)

Critical changes are always led first in the report, regardless of the order they appear in the ruleset.

---

## No-Change Case

If the two snapshots are identical, the report will be:

```
No changes detected between the two snapshots. The iptables ruleset is identical.
```

This is the correct result when comparing a file with itself or when no change occurred between two captures.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `BEFORE_MISSING` / `AFTER_MISSING` | Check both paths; use absolute paths |
| `Error: Required scripts not found` | Re-run the install step for both `.py` files |
| `Failed to parse` | Ensure both files are `iptables-save` output |
| `Failed to compute diff` | Check both parsed JSONs are non-empty |
| Report misses a change | Verify both snapshots bracket the actual change window |

---

## Using the Scripts Standalone

Both scripts can be used independently of the Claude skill:

```bash
# Parse snapshot to JSON
python3 iptables_parser.py before.txt > before.json
python3 iptables_parser.py after.txt  > after.json

# Compute diff
python3 iptables_diff.py before.json after.json

# Pipe into jq
python3 iptables_diff.py before.json after.json | jq '.summary'
python3 iptables_diff.py before.json after.json | jq '.changes.policy_changes'
python3 iptables_diff.py before.json after.json | jq '.has_critical_changes'
```

The JSON schemas are documented in `docs/overview.md`.
