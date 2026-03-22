# iptables-diff-explain — Claude Code Skill

## Description

Compares two `iptables-save` snapshot files (before and after a change) and produces a plain-English explanation of what changed, why it matters, and what the security impact is. No API key required — analysis is performed natively by Claude.

## When to Use

Invoke when the user:
- Has two `iptables-save` files and wants to know what changed between them
- Is reviewing a change window and needs to understand the firewall delta
- Uses `/iptables-diff-explain` explicitly
- Asks "what changed in the firewall?" or "what did the hardening script do?"

## Invocation

```
/iptables-diff-explain <before.txt> <after.txt>
```

Where both files are the output of `iptables-save`. `before.txt` is the baseline (earlier), `after.txt` is the current (later) state.

---

## Execution Steps

### Step 1 — Parse Arguments

Extract from the invocation:
- `BEFORE`: required — path to the baseline `iptables-save` file
- `AFTER`: required — path to the current `iptables-save` file

If either is missing, respond with:
```
Usage: /iptables-diff-explain <before.txt> <after.txt>

Where both files are the output of: iptables-save > snapshot.txt
  before.txt  — baseline (captured before the change)
  after.txt   — current state (captured after the change)

Example: /iptables-diff-explain /tmp/before.txt /tmp/after.txt
```
Stop here.

---

### Step 2 — Pre-flight Checks

**Check 1: Both files exist**
```bash
test -f "<BEFORE>" && echo "BEFORE_OK" || echo "BEFORE_MISSING"
test -f "<AFTER>" && echo "AFTER_OK" || echo "AFTER_MISSING"
```
If either is missing, report which file was not found. Stop.

**Check 2: Scripts are installed**
```bash
ls ~/.claude/skills/iptables-diff-explain/iptables_parser.py 2>/dev/null && echo "FOUND" || echo "NOT_FOUND"
ls ~/.claude/skills/iptables-diff-explain/iptables_diff.py 2>/dev/null && echo "FOUND" || echo "NOT_FOUND"
```
If either NOT_FOUND:
```
Error: Required scripts not found at ~/.claude/skills/iptables-diff-explain/
Install them by copying from the skill repo:
  cp <repo>/iptables-diff-explain/.claude/skills/iptables-diff-explain/*.py \
     ~/.claude/skills/iptables-diff-explain/
```
Stop.

**Check 3: python3 is available**
```bash
python3 --version 2>&1
```
If not found: `Error: python3 is not installed or not on PATH.` Stop.

---

### Step 3 — Parse Both Snapshots

Parse each file to JSON, writing to temp files:

```bash
python3 ~/.claude/skills/iptables-diff-explain/iptables_parser.py "<BEFORE>" > /tmp/iptables_before_$$.json
python3 ~/.claude/skills/iptables-diff-explain/iptables_parser.py "<AFTER>"  > /tmp/iptables_after_$$.json
```

If either parser exits non-zero or produces empty output:
```
Error: Failed to parse one or both files as iptables-save output.
Ensure both files are the output of 'iptables-save' or 'iptables-save -c'.
```
Stop.

---

### Step 4 — Compute the Diff

```bash
python3 ~/.claude/skills/iptables-diff-explain/iptables_diff.py \
  /tmp/iptables_before_$$.json /tmp/iptables_after_$$.json
```

Capture the diff JSON output. Then clean up:
```bash
rm -f /tmp/iptables_before_$$.json /tmp/iptables_after_$$.json
```

If the diff exits non-zero or produces no output:
```
Error: Failed to compute diff between the two snapshots.
```
Stop.

---

### Step 5 — Analyse and Explain

Read the diff JSON from Step 4. Apply the analysis framework below and produce the explanation.

---

## Analysis Framework

You are an iptables security expert. The diff JSON has this structure:
```
{
  "diff_at": "<timestamp>",
  "drift_detected": true|false,
  "has_critical_changes": true|false,
  "summary": {
    "tables_added": N, "tables_removed": N,
    "chains_added": N, "chains_removed": N,
    "policy_changes": N,
    "rules_added": N, "rules_removed": N,
    "rules_repositioned": N
  },
  "changes": {
    "policy_changes": [ { "table": "...", "chain": "...", "before": "...", "after": "..." } ],
    "chains_added":   [ { "table": "...", "chain": "...", "type": "...", "rule_count": N, "rules": [...] } ],
    "chains_removed": [ { "table": "...", "chain": "...", "type": "...", "rule_count": N, "rules": [...] } ],
    "rules_added":    [ { "table": "...", "chain": "...", "position": N, "target": "...", "raw_rule": "..." } ],
    "rules_removed":  [ { "table": "...", "chain": "...", "position": N, "target": "...", "raw_rule": "..." } ],
    "rules_repositioned": [ { "table": "...", "chain": "...", "old_position": N, "new_position": N, "raw_rule": "..." } ]
  }
}
```

### What to Analyse

**1. No-Change Case**
If `drift_detected` is false, respond:
```
No changes detected between the two snapshots. The iptables ruleset is identical.
```
Stop — no further analysis needed.

**2. Policy Changes (highest impact — always lead with these)**
A policy change on INPUT/FORWARD/OUTPUT is the single highest-impact iptables change. `ACCEPT → DROP` means every unmatched packet is now silently dropped. Call this out prominently.

**3. Chains Added**
Each entry includes the full `rules` list — explain what the chain does based on its rules. Identify known patterns:
- `f2b-*` → fail2ban ban chain just created; list the banned IPs
- `DOCKER*` → Docker daemon started; explain each stage's purpose
- Unknown → describe what the rules indicate about intent

**4. Chains Removed**
What protection or functionality was removed? Were active bans cleared?

**5. Rules Added**
For each added rule: what traffic does it now affect? Is it a tightening (new DROP/REJECT) or loosening (new ACCEPT)?

**6. Rules Removed**
What was previously blocked or allowed that no longer is?

**7. Rules Repositioned**
Repositioning changes evaluation order. Explain if any repositioning causes a rule to be shadowed or newly reachable.

**8. Overall Impact**
One clear verdict: did the change tighten or loosen the firewall posture? What is the net security impact?

---

## Output Format

```markdown
# iptables Ruleset Change Explanation
*AI-generated analysis — verify against raw diff and snapshots before acting on findings.*
*Scope: iptables rules only. Azure NSG, cloud firewall, and routing table not included.*

## Change Summary
<X rules added, Y rules removed, Z policy changes — one sentence on the nature of the change>

## Security Impact

### Policy Changes
<if any — call these out prominently with before/after and blast radius>

### Rules Added
<bullet per rule: what it matches, what it does, tightening or loosening>

### Rules Removed
<bullet per rule: what protection or access was revoked>

### Chains Added / Removed
<for each: name, purpose, rules inside, known pattern if recognised>

### Rules Repositioned
<only if repositioning changes effective behaviour — omit if cosmetic>

## Overall Assessment
<2-3 sentence verdict: tightening or loosening, blast radius, what to verify>

## Recommended Actions
<only if critical changes found — specific actions to verify or remediate>
```
