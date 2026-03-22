# Test Plan: nftables-diff-explain Skill

## Test Fixtures

All fixtures are in `examples/`.

| File | Role |
|---|---|
| `examples/fx-03-inet-drop-policy.json` | Baseline — inet table, INPUT+FORWARD DROP, 3 rules |
| `examples/fx-12-icmp-ct.json` | After — ICMP type filtering, ct direction/mark/zone |

Additional diff pairs available in the `netfilter-inspector` source project:

| Before | After | Key Change |
|---|---|---|
| `fx-02-ip-clean.json` | `fx-03-inet-drop-policy.json` | ip table replaced by inet, DROP policies added |
| `fx-02-ip-clean.json` | `fx-09-nat.json` | ip table replaced, NAT table added |
| `fx-03-inet-drop-policy.json` | `fx-05-sets.json` | Named set chain added |

---

## Test Scenarios

### T1 — ICMP/CT rule replacement (sample fixtures)

```
/nftables-diff-explain examples/fx-03-inet-drop-policy.json examples/fx-12-icmp-ct.json
```

**Expected:**
- drift_detected: true, has_critical_changes: true
- 2 chains removed (forward, output — both empty, removal loosens forward posture)
- 7 rules added: IPv4 ping, IPv6 ping, ND solicitation, non-redirect ICMP, ct mark, ct direction SSH, ct zone DROP
- 3 rules removed: established/related, all-ICMP, SSH new
- Parse warnings about handle reuse acknowledged
- Critical finding: removal of `ct state established,related` leaves non-SSH established sessions unprotected
- Critical finding: forward chain removal re-enables packet forwarding

### T2 — ip → inet table replacement

```
/nftables-diff-explain <path>/fx-02-ip-clean.json <path>/fx-03-inet-drop-policy.json
```

**Expected:**
- ip table removed, inet table added
- INPUT and FORWARD policy now DROP (critical)
- inet family now covers both IPv4 and IPv6

### T3 — NAT table addition

```
/nftables-diff-explain <path>/fx-02-ip-clean.json <path>/fx-09-nat.json
```

**Expected:**
- NAT chain added; DNAT/MASQUERADE rules explained
- critical_changes: true (new table with nat chain)

### T4 — No-change case

```
/nftables-diff-explain examples/fx-03-inet-drop-policy.json examples/fx-03-inet-drop-policy.json
```

**Expected:** `No changes detected between the two snapshots. The nftables ruleset is identical.`

### T5 — Error: plain-text input

Provide `nft list ruleset` (without `--json`) as input.

**Expected:** `Failed to parse one or both files as nft --json list ruleset output.`

### T6 — Error: missing file

```
/nftables-diff-explain examples/fx-03-inet-drop-policy.json /tmp/does-not-exist.json
```

**Expected:** `AFTER_MISSING` error with file path.

---

## Differ Unit Tests

The `nftables_diff.py` is verified against pre-computed reference diffs:

```bash
python3 nftables_parser.py fx-03-inet-drop-policy.json > b.json
python3 nftables_parser.py fx-12-icmp-ct.json > a.json
python3 nftables_diff.py b.json a.json | python3 -c "
import sys, json; d=json.load(sys.stdin)
assert d['drift_detected'] == True
assert d['has_critical_changes'] == True
assert d['summary']['rules_added'] == 7
assert d['summary']['rules_removed'] == 3
assert d['summary']['chains_removed'] == 2
print('All assertions passed')
"
```

Reference diff files: `*_diff.json` alongside fixtures in the netfilter-inspector source project.

---

## Ground Truth Verification

```bash
python3 nftables_diff.py b.json a.json > computed_diff.json
python3 -c "
import json
c = json.load(open('computed_diff.json'))
r = json.load(open('fx-03-inet-drop-policy_vs_fx-12-icmp-ct_diff.json'))
assert c['summary'] == r['summary'], f'Summary mismatch'
assert c['drift_detected'] == r['drift_detected']
assert c['has_critical_changes'] == r['has_critical_changes']
print('Ground truth: OK')
"
```
