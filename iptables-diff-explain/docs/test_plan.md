# Test Plan: iptables-diff-explain Skill

## Test Fixtures

All sample fixtures are in `examples/`.

| File | Role |
|---|---|
| `examples/ubuntu2404-clean.txt` | Baseline — security table only, no filter table |
| `examples/ubuntu2404-cis-hardened.txt` | After CIS hardening — filter table with DROP policies |

Additional diff pairs available in the `netfilter-inspector` source project:

| Before | After | Key Change |
|---|---|---|
| `ubuntu2404-clean.txt` | `ubuntu2404-docker.txt` | Docker installed: 16 chains added |
| `ubuntu2404-docker.txt` | `ubuntu2404-docker-fail2ban.txt` | fail2ban added: f2b-sshd chain + 1 ban |
| `ubuntu2404-docker-fail2ban.txt` | `ubuntu2404-docker-fail2ban-wireguard.txt` | WireGuard: 3 rules added |
| `ubuntu2404-clean.txt` | `ubuntu2404-log-mark-snat.txt` | Logging + MARK + SNAT: 12 chains added |

---

## Test Scenarios

### T1 — CIS hardening diff (sample fixtures)

```
/iptables-diff-explain examples/ubuntu2404-clean.txt examples/ubuntu2404-cis-hardened.txt
```

**Expected:**
- drift_detected: true, has_critical_changes: true
- 1 table added (filter), 1 table removed (security)
- 3 chains added (filter/INPUT DROP, filter/FORWARD DROP, filter/OUTPUT ACCEPT)
- 3 chains removed (security/INPUT, security/FORWARD, security/OUTPUT with Wire Server rules)
- Policy change section: INPUT effective ACCEPT→DROP, FORWARD effective ACCEPT→DROP
- Notable finding: Wire Server output controls removed

### T2 — Docker installation

```
/iptables-diff-explain <path>/ubuntu2404-clean.txt <path>/ubuntu2404-docker.txt
```

**Expected:**
- 16 chains added across filter, nat, raw tables
- Docker chain topology explained (DOCKER-FORWARD, DOCKER-CT, DOCKER-BRIDGE)
- Port 8080 DNAT noted as notable finding

### T3 — fail2ban adding a ban

```
/iptables-diff-explain <path>/ubuntu2404-docker.txt <path>/ubuntu2404-docker-fail2ban.txt
```

**Expected:**
- 1 chain added (f2b-sshd), 1 rule added (INPUT → f2b-sshd)
- Active ban 1.2.3.4/32 identified in the f2b-sshd chain content

### T4 — No-change case

```
/iptables-diff-explain examples/ubuntu2404-clean.txt examples/ubuntu2404-clean.txt
```

**Expected:** `No changes detected between the two snapshots. The iptables ruleset is identical.`

### T5 — Error: reversed argument order

Invoke with before/after swapped. **Expected:** Diff detects drift; rules/chains flagged as removed are actually the expected additions. The report will note the net effect is loosening if the actual change was tightening.  Use this to verify the skill correctly identifies which snapshot is baseline.

### T6 — Error: missing file

```
/iptables-diff-explain examples/ubuntu2404-clean.txt /tmp/does-not-exist.txt
```

**Expected:** `AFTER_MISSING` error with file path.

---

## Differ Unit Tests

The `iptables_diff.py` is verified against pre-computed reference diffs:

```bash
python3 iptables_parser.py ubuntu2404-clean.txt > b.json
python3 iptables_parser.py ubuntu2404-cis-hardened.txt > a.json
python3 iptables_diff.py b.json a.json | python3 -c "
import sys, json; d=json.load(sys.stdin)
assert d['drift_detected'] == True
assert d['has_critical_changes'] == True
assert d['summary']['tables_added'] == 1
assert d['summary']['tables_removed'] == 1
assert d['summary']['chains_added'] == 3
print('All assertions passed')
"
```

Reference diff files: `*_diff.json` alongside fixtures in the netfilter-inspector source project.

---

## Ground Truth Verification

```bash
# Verify computed diff matches reference
python3 iptables_diff.py before.json after.json > computed_diff.json
python3 -c "
import json
c = json.load(open('computed_diff.json'))
r = json.load(open('ubuntu2404-clean_vs_ubuntu2404-cis-hardened_diff.json'))
assert c['summary'] == r['summary'], f'Summary mismatch: {c[\"summary\"]} vs {r[\"summary\"]}'
assert c['drift_detected'] == r['drift_detected']
assert c['has_critical_changes'] == r['has_critical_changes']
print('Ground truth: OK')
"
```
