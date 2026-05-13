---
name: iptables-explain
description: Use when the user provides a single iptables-save snapshot file and wants to understand what the rules are doing, the firewall posture of a Linux host, or what specific iptables rules mean. Trigger phrases include "what does this iptables config do", "explain my iptables rules", "is this firewall secure", "analyze my iptables ruleset", "what is my iptables doing". Do NOT use when the user has two snapshots to compare (use iptables-diff-explain), for nftables rules (use nftables-explain), or for questions about iptables without providing a snapshot file.
---

# iptables-explain — Claude Code Skill

## Description

Reads an `iptables-save` snapshot file and produces a plain-English security analysis of the ruleset. Explains default policies, DROP/REJECT rules, custom chains, and overall firewall posture. No API key required — analysis is performed natively by Claude.

## When to Use

Invoke when the user:
- Provides an `iptables-save` output file and asks what the rules are doing
- Wants to understand the firewall posture of a Linux host
- Uses `/iptables-explain` explicitly
- Asks "what does this iptables config do?" or "is this firewall secure?"

## Invocation

```
/iptables-explain <snapshot.txt>
```

Where `snapshot.txt` is the output of `iptables-save` (or `iptables-save -c`).

---

## Execution Steps

### Step 1 — Parse Arguments

Extract from the invocation:
- `FILE`: required — path to an `iptables-save` output file

If no file path is provided, respond with:
```
Usage: /iptables-explain <snapshot.txt>

Where snapshot.txt is the output of: iptables-save > snapshot.txt

Example: /iptables-explain /tmp/before.txt
```
Stop here.

---

### Step 2 — Pre-flight Checks

Run the following checks using Bash. Fail fast with a clear message.

**Check 1: File exists**
```bash
test -f "<FILE>" && echo "OK" || echo "NOT_FOUND"
```
If NOT_FOUND: `Error: File not found: <FILE>`  Stop.

**Check 2: iptables_parser.py is installed**
```bash
ls ~/.claude/skills/iptables-explain/iptables_parser.py 2>/dev/null && echo "FOUND" || echo "NOT_FOUND"
```
If NOT_FOUND:
```
Error: iptables_parser.py not found at ~/.claude/skills/iptables-explain/
Install it by copying it from the skill repo:
  cp <repo>/iptables-explain/.claude/skills/iptables-explain/iptables_parser.py \
     ~/.claude/skills/iptables-explain/
```
Stop.

**Check 3: python3 is available**
```bash
python3 --version 2>&1
```
If not found: `Error: python3 is not installed or not on PATH.`  Stop.

---

### Step 3 — Parse the Snapshot

Run the parser to convert the iptables-save file to structured JSON:

```bash
python3 ~/.claude/skills/iptables-explain/iptables_parser.py "<FILE>"
```

Capture the JSON output. If the parser exits non-zero or produces no output:
```
Error: Failed to parse <FILE> as iptables-save output.
Ensure the file is the output of 'iptables-save' or 'iptables-save -c'.
```
Stop.

---

### Step 4 — Analyse and Explain

Read the JSON output from Step 3. Apply the analysis framework below and produce the explanation.

---

## Analysis Framework

You are an iptables security expert. The JSON from the parser has this structure:
```
{
  "framework": "iptables-nft" | "iptables-legacy",
  "family": "ipv4" | "ipv6",
  "input_format": "iptables-save" | "ip6tables-save" | ...,
  "tables": {
    "<table>": {
      "chains": {
        "<chain>": {
          "type": "builtin" | "user-defined",
          "default_policy": "ACCEPT" | "DROP" | null,
          "rules": [ ... ]
        }
      }
    }
  },
  "diagnostics": {
    "drop_policy_chains": [...],
    "user_defined_chains": { "<chain>": { "referenced_from": [...] } },
    "nat_summary": { "masquerade_rules": [...], "dnat_rules": [...] }
  }
}
```

Each rule object has: `position`, `target`, `target_params`, `protocol`, `source`, `destination`, `in_interface`, `out_interface`, `dst_port`, `src_port`, `match_extensions`, `raw_rule`.

### What to Analyse

**1. Framework**
Read `framework` from the JSON (`"iptables-nft"` or `"iptables-legacy"`). State it and explain briefly:
- `iptables-nft`: iptables CLI using the nftables kernel backend (common on Ubuntu 20.04+, Debian 11+)
- `iptables-legacy`: iptables using the legacy xtables kernel backend (older systems)
Note: both use identical rule syntax — the distinction matters for co-existence with native nft rules.

**2. Default Policies**
For each chain with a non-ACCEPT default policy, call it out explicitly. An INPUT chain with policy DROP is the highest-impact single firewall setting — every unmatched inbound packet is silently dropped.

**3. Rules — Chain by Chain**
For each table and chain that has rules, explain in plain English what each rule does. Focus on:
- What traffic does it match? (protocol, port, source IP, interface)
- What happens to it? (ACCEPT, DROP, REJECT, LOG, jump to custom chain)
- Why does it exist? (e.g. "allows established connections to return", "permits SSH from anywhere")

Skip chains with zero rules and ACCEPT default policy — they are pass-through and need no explanation.

**4. Custom Chains**
Identify and explain every user-defined chain:
- `f2b-*` chains → fail2ban ban chains. List active bans (source IPs that hit REJECT/DROP before RETURN).
- `DOCKER*` chains → Docker networking. Explain isolation stage purpose.
- `ufw-*` chains → UFW (Uncomplicated Firewall) managed rules.
- Unknown custom chains → describe what they appear to do based on their rules.

**5. Security Posture Summary**
Conclude with a plain-English verdict:
- Is the host default-deny inbound? (INPUT policy DROP or REJECT)
- What inbound ports/protocols are explicitly permitted?
- Is forwarding enabled or locked down?
- Are there any rules that stand out as overly permissive or suspicious?

---

## Output Format

```markdown
# iptables Ruleset Explanation
*AI-generated analysis — verify against raw snapshot before acting on findings.*
*Scope: iptables rules only. Azure NSG, cloud firewall, and routing table not included.*

## Framework
<framework name and brief description>

## Default Policies
<table listing chain → policy, highlighting any DROP/REJECT policies>

## Rules

### filter table
#### INPUT chain
<plain-English explanation of each rule>

#### FORWARD chain
<plain-English explanation>

#### OUTPUT chain
<plain-English explanation — omit if all ACCEPT and no rules>

#### <custom chains>
<explanation, identify known patterns (fail2ban, Docker, UFW)>

### nat table
<explanation if rules present>

### <other tables>
<explanation if rules present>

## Security Posture Summary
<2-4 sentence verdict on the overall firewall posture>

## Notable Findings
<bullet list of anything that warrants attention: overly permissive rules, active bans, Docker isolation issues, default-deny with missing explicit allows, etc. Omit section if nothing notable.>
```
