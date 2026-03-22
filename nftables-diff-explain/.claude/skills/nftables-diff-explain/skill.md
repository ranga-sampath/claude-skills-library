# nftables-diff-explain — Claude Code Skill

## Description

Compares two `nft --json list ruleset` snapshot files (before and after a change) and produces a plain-English explanation of what changed, why it matters, and what the security impact is. No API key required — analysis is performed natively by Claude.

## When to Use

Invoke when the user:
- Has two nftables JSON snapshots and wants to know what changed between them
- Is reviewing a change window and needs to understand the nftables delta
- Uses `/nftables-diff-explain` explicitly
- Asks "what changed in the nftables config?" or "what did the upgrade do to the firewall?"

## Invocation

```
/nftables-diff-explain <before.json> <after.json>
```

Where both files are the output of `nft --json list ruleset`. `before.json` is the baseline (earlier), `after.json` is the current (later) state.

---

## Execution Steps

### Step 1 — Parse Arguments

Extract from the invocation:
- `BEFORE`: required — path to the baseline nft JSON file
- `AFTER`: required — path to the current nft JSON file

If either is missing, respond with:
```
Usage: /nftables-diff-explain <before.json> <after.json>

Where both files are the output of: nft --json list ruleset > snapshot.json
  before.json — baseline (captured before the change)
  after.json  — current state (captured after the change)

Example: /nftables-diff-explain /tmp/before.json /tmp/after.json
```
Stop here.

---

### Step 2 — Pre-flight Checks

**Check 1: Both files exist**
```bash
test -f "<BEFORE>" && echo "BEFORE_OK" || echo "BEFORE_MISSING"
test -f "<AFTER>" && echo "AFTER_OK" || echo "AFTER_MISSING"
```
If either missing, report which file was not found. Stop.

**Check 2: Scripts are installed**
```bash
ls ~/.claude/skills/nftables-diff-explain/nftables_parser.py 2>/dev/null && echo "FOUND" || echo "NOT_FOUND"
ls ~/.claude/skills/nftables-diff-explain/nftables_diff.py   2>/dev/null && echo "FOUND" || echo "NOT_FOUND"
```
If either NOT_FOUND:
```
Error: Required scripts not found at ~/.claude/skills/nftables-diff-explain/
Install them by copying from the skill repo:
  cp <repo>/nftables-diff-explain/.claude/skills/nftables-diff-explain/*.py \
     ~/.claude/skills/nftables-diff-explain/
```
Stop.

**Check 3: python3 is available**
```bash
python3 --version 2>&1
```
If not found: `Error: python3 is not installed or not on PATH.` Stop.

---

### Step 3 — Parse Both Snapshots

```bash
python3 ~/.claude/skills/nftables-diff-explain/nftables_parser.py "<BEFORE>" > /tmp/nftables_before_$$.json
python3 ~/.claude/skills/nftables-diff-explain/nftables_parser.py "<AFTER>"  > /tmp/nftables_after_$$.json
```

If either parser exits non-zero or produces empty output:
```
Error: Failed to parse one or both files as nft --json list ruleset output.
Ensure both files are the output of: nft --json list ruleset > snapshot.json
```
Stop.

---

### Step 4 — Compute the Diff

```bash
python3 ~/.claude/skills/nftables-diff-explain/nftables_diff.py \
  /tmp/nftables_before_$$.json /tmp/nftables_after_$$.json
```

Capture the diff JSON output. Then clean up:
```bash
rm -f /tmp/nftables_before_$$.json /tmp/nftables_after_$$.json
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

You are an nftables security expert. The diff JSON has this structure:
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
    "rules_added":    [ { "table": "...", "chain": "...", "position": N, "verdict": "...", "protocol": "...", "src_addr": "...", "dst_addr": "...", "dst_port": "...", "ct_state": "...", "raw_expressions": [...] } ],
    "rules_removed":  [ { "table": "...", "chain": "...", "position": N, "verdict": "...", "protocol": "...", "src_addr": "...", "dst_addr": "...", "dst_port": "...", "ct_state": "...", "raw_expressions": [...] } ],
    "rules_repositioned": [ { "table": "...", "chain": "...", "old_position": N, "new_position": N, "verdict": "...", "raw_expressions": [...] } ]
  }
}
```

### What to Analyse

**1. No-Change Case**
If `drift_detected` is false:
```
No changes detected between the two snapshots. The nftables ruleset is identical.
```
Stop — no further analysis needed.

**2. Policy Changes (lead with these)**
A policy change on an input/forward/output base chain is the highest-impact single change. `accept → drop` means all unmatched packets are now silently dropped. Call this out prominently.

**3. Chains Added**
Each entry includes the full `rules` list. Explain what the chain does based on its rules. Identify known patterns:
- `DOCKER*` / `docker*` → Docker daemon networking chains
- `f2b-*` → fail2ban ban chain; list the banned IPs/ranges
- Unknown → describe what the rules indicate

**4. Chains Removed**
What protection or routing was removed? If a ban chain was removed, were active bans cleared?

**5. Rules Added**
For each added rule: what traffic does it now affect? Is it a tightening (new drop/reject) or loosening (new accept)?

**6. Rules Removed**
What was previously blocked or permitted that no longer is?

**7. Rules Repositioned**
Repositioning changes evaluation order in nftables. Explain if repositioning causes a rule to be shadowed or newly reachable.

**8. Overall Impact**
One clear verdict: did the change tighten or loosen the firewall posture? What is the net security impact?

---

## Output Format

```markdown
# nftables Ruleset Change Explanation
*AI-generated analysis — verify against raw diff and snapshots before acting on findings.*
*Scope: nftables rules only. Azure NSG, cloud firewall, and routing table not included.*

## Change Summary
<X rules added, Y removed, Z policy changes — one sentence on the nature of the change>

## Security Impact

### Policy Changes
<if any — call out prominently with before/after and blast radius>

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
