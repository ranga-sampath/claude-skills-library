# nftables-explain — Claude Code Skill

## Description

Reads an `nft --json list ruleset` snapshot file and produces a plain-English security analysis of the ruleset. Explains default policies, drop/reject rules, custom chains, sets, and overall firewall posture. No API key required — analysis is performed natively by Claude.

## When to Use

Invoke when the user:
- Provides an nftables JSON snapshot and asks what the rules are doing
- Wants to understand the firewall posture of a host running native nftables
- Uses `/nftables-explain` explicitly
- Asks "what does this nftables config do?" or "is this nftables setup secure?"

## Invocation

```
/nftables-explain <snapshot.json>
```

Where `snapshot.json` is the output of `nft --json list ruleset`.

---

## Execution Steps

### Step 1 — Parse Arguments

Extract from the invocation:
- `FILE`: required — path to an `nft --json list ruleset` JSON file

If no file path is provided, respond with:
```
Usage: /nftables-explain <snapshot.json>

Where snapshot.json is the output of: nft --json list ruleset > snapshot.json

Example: /nftables-explain /tmp/current.json
```
Stop here.

---

### Step 2 — Pre-flight Checks

**Check 1: File exists**
```bash
test -f "<FILE>" && echo "OK" || echo "NOT_FOUND"
```
If NOT_FOUND: `Error: File not found: <FILE>` Stop.

**Check 2: nftables_parser.py is installed**
```bash
ls ~/.claude/skills/nftables-explain/nftables_parser.py 2>/dev/null && echo "FOUND" || echo "NOT_FOUND"
```
If NOT_FOUND:
```
Error: nftables_parser.py not found at ~/.claude/skills/nftables-explain/
Install it by copying it from the skill repo:
  cp <repo>/nftables-explain/.claude/skills/nftables-explain/nftables_parser.py \
     ~/.claude/skills/nftables-explain/
```
Stop.

**Check 3: python3 is available**
```bash
python3 --version 2>&1
```
If not found: `Error: python3 is not installed or not on PATH.` Stop.

---

### Step 3 — Parse the Snapshot

Run the parser to convert the nft JSON to structured form:

```bash
python3 ~/.claude/skills/nftables-explain/nftables_parser.py "<FILE>"
```

Capture the JSON output. If the parser exits non-zero or produces no output:
```
Error: Failed to parse <FILE> as an nft --json list ruleset output.
Ensure the file is the output of: nft --json list ruleset > snapshot.json
```
Stop.

---

### Step 4 — Analyse and Explain

Read the JSON output from Step 3. Apply the analysis framework below and produce the explanation.

---

## Analysis Framework

You are an nftables security expert. The JSON from the parser has this structure:
```
{
  "parsed_at": "<timestamp>",
  "tables": {
    "<family> <table>": {
      "family": "ip" | "ip6" | "inet" | "arp" | "bridge" | "netdev",
      "name": "<table_name>",
      "chains": {
        "<chain>": {
          "type": "filter" | "nat" | "route",
          "hook": "input" | "forward" | "output" | "prerouting" | "postrouting",
          "priority": N,
          "default_policy": "accept" | "drop",
          "rules": [
            { "position": N, "verdict": "accept|drop|reject|return|jump|goto",
              "protocol": "...", "src_addr": "...", "dst_addr": "...",
              "dst_port": "...", "src_port": "...", "ct_state": "...",
              "in_interface": "...", "out_interface": "...",
              "icmp_type": "...", "comment": "...",
              "set_references": ["<setname>"],
              "raw_expressions": [ ... ]  }
          ]
        }
      },
      "sets": { "<set_name>": { "type": "...", "elements": [...] } }
    }
  }
}
```

### What to Analyse

**1. Tables and Families**
State which address families are covered (ip = IPv4, ip6 = IPv6, inet = both). Note if IPv6 is not covered.

**2. Default Policies**
For each base chain (one with a hook), state the default policy. A `drop` policy on an `input` hook is the highest-impact single setting — all unmatched inbound packets are silently dropped.

**3. Rules — Chain by Chain**
For each chain that has rules, explain in plain English:
- What traffic does each rule match? (use `protocol`, `src_addr`, `dst_addr`, `dst_port`, `ct_state`, `in_interface`, `icmp_type`)
- What happens to it? (use `verdict`, `jump_target`, `goto_target`)
- Why does it exist?

If a rule has `set_references`, it matches against a named set — look up the set under `tables.<table>.sets.<name>` to explain what the set contains.
For complex/opaque rules where structured fields are absent, consult `raw_expressions` — it contains the raw nft JSON expressions.

Skip chains with zero rules and `accept` default policy.

**4. Sets**
If sets are defined, explain what they contain and how they are used (e.g. "allowed-ports contains {22, 80, 443} — used to permit inbound TCP on those ports").

**5. Known Patterns**
- Chains named `DOCKER*` or `docker*` → Docker networking integration
- Chains named `f2b-*` → fail2ban integration
- `reject with icmp type port-unreachable` → service-level port closed response
- `ct state established,related accept` → stateful connection tracking (standard practice)

**6. Security Posture Summary**
- Is the host default-deny inbound?
- What inbound ports/protocols are explicitly permitted?
- Is forwarding enabled or locked down?
- Any rules that appear overly permissive or suspicious?

---

## Output Format

```markdown
# nftables Ruleset Explanation
*AI-generated analysis — verify against raw snapshot before acting on findings.*
*Scope: nftables rules only. Azure NSG, cloud firewall, and routing table not included.*

## Address Families Covered
<which families (ip, ip6, inet) are present>

## Default Policies
<table listing hook chain → policy, highlighting any drop policies>

## Rules

### <table name> (<family>)
#### <chain name> (<hook>, priority <N>)
<plain-English explanation of each rule>

#### <custom chains>
<explanation, identify known patterns>

## Sets
<if any — name, contents, how used. Omit section if no sets.>

## Security Posture Summary
<2-4 sentence verdict on the overall firewall posture>

## Notable Findings
<bullet list of anything warranting attention. Omit if nothing notable.>
```
