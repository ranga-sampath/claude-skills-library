# Test Plan: nftables-explain Skill

## Test Fixtures

All fixtures are in `examples/`.

| Fixture | Description | Key Features to Verify |
|---|---|---|
| `examples/fx-03-inet-drop-policy.json` | inet table, INPUT+FORWARD DROP, 3 rules | inet family, drop policies, conntrack, SSH |

Additional fixtures available in the `netfilter-inspector` source project:

| Fixture | Key Features |
|---|---|
| `fx-01-empty.json` | No tables or rules — empty ruleset |
| `fx-02-ip-clean.json` | IPv4-only, ACCEPT defaults |
| `fx-04-regular-chains.json` | User-defined chains (non-base) |
| `fx-05-sets.json` | Named sets (blocklist, port-map), unresolved set reference |
| `fx-06-multi-family.json` | ip + inet tables coexisting |
| `fx-07-inet-ip-mixed.json` | inet + ip with overlapping hooks |
| `fx-08-counters.json` | Rules with packet/byte counters |
| `fx-09-nat.json` | NAT table with DNAT/MASQUERADE |
| `fx-10-negation-ports-interfaces.json` | Negated match conditions |
| `fx-11-log-return-reject-goto.json` | LOG, RETURN, REJECT, goto targets |
| `fx-12-icmp-ct.json` | ICMP type filtering, ct direction, ct mark, ct zone |

---

## Test Scenarios

### T1 — Drop-policy inet table (sample fixture)

```
/nftables-explain examples/fx-03-inet-drop-policy.json
```

**Expected:**
- Address family: `inet` (covers both IPv4 and IPv6)
- input hook: DROP policy called out prominently
- forward hook: DROP policy, no rules
- 3 rules explained: ct state established/related, ICMP accept, TCP/22 new
- Notable: all ICMP accepted without type filtering, SSH open to all

### T2 — Named sets

```
/nftables-explain <path>/fx-05-sets.json
```

**Expected:**
- Sets section: `blocklist` with 3 CIDR prefixes listed
- Rules referencing `@blocklist` explained in context of the set contents
- Unresolved set reference (`@allowlist`) flagged as notable finding

### T3 — NAT table

```
/nftables-explain <path>/fx-09-nat.json
```

**Expected:**
- NAT table identified and explained
- DNAT/MASQUERADE rules described

### T4 — Empty ruleset

```
/nftables-explain <path>/fx-01-empty.json
```

**Expected:** No tables or chains present; ruleset is empty.

### T5 — Multi-family (ip + inet coexistence)

```
/nftables-explain <path>/fx-06-multi-family.json
```

**Expected:**
- Both `ip` and `inet` tables identified
- Notable: IPv4 traffic passes through both tables; potential for double-processing

### T6 — Error: plain-text nft output

Provide `nft list ruleset` (without `--json`) output.

**Expected:** `Failed to parse as nft --json list ruleset output.`

### T7 — Error: missing file

```
/nftables-explain /tmp/does-not-exist.json
```

**Expected:** `Error: File not found`

---

## Parser Unit Tests

The `nftables_parser.py` has a full unit test suite in the `netfilter-inspector` source project:

```bash
cd <netfilter-inspector>/nftables-parser
python3 -m pytest tests/ -q
```

Tests cover: all 12 fixtures, all match types, sets, maps, conntrack directives, ICMP, negations, logging, goto/jump targets.

---

## Ground Truth Verification

Parser output is verified against pre-computed reference snapshots:

```bash
python3 nftables_parser.py fx-03-inet-drop-policy.json > computed.json
python3 -c "
import json
c = json.load(open('computed.json'))
r = json.load(open('fx-03-inet-drop-policy_snapshot.json'))
for tname, t in r.get('tables', {}).items():
    for cname, c_chain in t.get('chains', {}).items():
        computed_chain = c['tables'][tname]['chains'][cname]
        assert len(computed_chain['rules']) == len(c_chain['rules']), f'{tname}/{cname} rule count mismatch'
print('Ground truth: OK')
"
```
