#!/usr/bin/env python3
"""Generate synthetic pcap pairs for endpoint-correlation mode testing.

Each function creates a (source, destination) pair representing the same
network path captured simultaneously at both ends. The source capture shows
all packets sent; the destination capture shows only what actually arrived —
the difference reveals drops, blocks, and path asymmetry.

Scenarios:
    1. clean_path        — all packets delivered, path is healthy
    2. syn_block         — firewall drops all SYNs before reaching destination
    3. partial_drop      — ~40% mid-stream packet loss, retransmissions at source
    4. icmp_reject       — firewall actively rejects with ICMP Admin Prohibited

Requires scapy:
    pip install scapy
    # or from the nw-forensics venv:
    source ../nw-forensics/agentic-pcap-forensic-engine/.venv/bin/activate

Usage:
    cd pcap-forensics/tests
    python3 generate_endpoint_correlation_pcaps.py
    # Creates: tests/sample_pcaps/endpoint_correlation/<scenario>_source.pcap
    #          tests/sample_pcaps/endpoint_correlation/<scenario>_dest.pcap
"""
from __future__ import annotations

from pathlib import Path

from scapy.all import (
    ARP, DNS, DNSQR, DNSRR, Ether, ICMP, IP, TCP, UDP, Raw,
    wrpcap, conf,
)

conf.verb = 0  # suppress scapy output

OUTPUT_DIR = Path(__file__).parent / "sample_pcaps" / "endpoint_correlation"
BASE_TIME = 1700000000.0

# Network topology
SOURCE_MAC  = "aa:bb:cc:dd:ee:01"
DEST_MAC    = "aa:bb:cc:dd:ee:02"
FW_MAC      = "aa:bb:cc:dd:ee:fe"   # firewall (inline between source and dest)
SOURCE_IP   = "10.0.1.10"
DEST_IP     = "10.0.2.20"
FIREWALL_IP = "10.0.1.1"


def _ts(offset: float) -> float:
    return BASE_TIME + offset


def _write_pair(name: str,
                source_pkts: list[tuple],
                dest_pkts: list[tuple]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    src_path  = OUTPUT_DIR / f"{name}_source.pcap"
    dest_path = OUTPUT_DIR / f"{name}_dest.pcap"

    src_list = []
    for pkt, ts in sorted(source_pkts, key=lambda x: x[1]):
        pkt.time = ts
        src_list.append(pkt)
    wrpcap(str(src_path), src_list)

    dst_list = []
    for pkt, ts in sorted(dest_pkts, key=lambda x: x[1]):
        pkt.time = ts
        dst_list.append(pkt)
    wrpcap(str(dest_path), dst_list)

    print(f"  {name}_source.pcap  ({len(src_list)} pkts)")
    print(f"  {name}_dest.pcap    ({len(dst_list)} pkts)")


# ---------------------------------------------------------------------------
# Scenario 1 — Clean Path
# All packets delivered. Source and destination see the same flows.
# Expected verdict: CLEAN PATH, HIGH confidence.
# ---------------------------------------------------------------------------

def gen_clean_path() -> None:
    """Healthy path: 3 TCP streams all delivered end-to-end."""
    src_pkts: list[tuple] = []
    dst_pkts: list[tuple] = []

    t = 0.0
    for stream_num in range(3):
        sport = 50000 + stream_num
        dport = 80
        seq_s = 1000 + stream_num * 100
        seq_d = 2000 + stream_num * 100
        t += stream_num * 2.0

        # SYN — visible at both ends
        syn = (
            Ether(src=SOURCE_MAC, dst=DEST_MAC) /
            IP(src=SOURCE_IP, dst=DEST_IP) /
            TCP(sport=sport, dport=dport, flags="S", seq=seq_s, window=65535),
            _ts(t)
        )
        t += 0.010; seq_s += 1

        # SYN-ACK — dest sends, source receives
        synack = (
            Ether(src=DEST_MAC, dst=SOURCE_MAC) /
            IP(src=DEST_IP, dst=SOURCE_IP) /
            TCP(sport=dport, dport=sport, flags="SA", seq=seq_d, ack=seq_s, window=65535),
            _ts(t)
        )
        t += 0.010; seq_d += 1

        # ACK — source sends
        ack = (
            Ether(src=SOURCE_MAC, dst=DEST_MAC) /
            IP(src=SOURCE_IP, dst=DEST_IP) /
            TCP(sport=sport, dport=dport, flags="A", seq=seq_s, ack=seq_d, window=65535),
            _ts(t)
        )
        t += 0.005

        # Data — source to dest (5 segments per stream)
        data_pkts = []
        for i in range(5):
            payload = f"GET /data{i} HTTP/1.1\r\nHost: server\r\n\r\n".encode()
            pkt = (
                Ether(src=SOURCE_MAC, dst=DEST_MAC) /
                IP(src=SOURCE_IP, dst=DEST_IP) /
                TCP(sport=sport, dport=dport, flags="A",
                    seq=seq_s, ack=seq_d, window=65535) /
                Raw(load=payload),
                _ts(t)
            )
            data_pkts.append(pkt)
            t += 0.005
            seq_s += len(payload)

        # ACK from dest for data
        data_ack = (
            Ether(src=DEST_MAC, dst=SOURCE_MAC) /
            IP(src=DEST_IP, dst=SOURCE_IP) /
            TCP(sport=dport, dport=sport, flags="A", seq=seq_d, ack=seq_s, window=65535),
            _ts(t)
        )
        t += 0.005

        # FIN teardown
        fin_s = (
            Ether(src=SOURCE_MAC, dst=DEST_MAC) /
            IP(src=SOURCE_IP, dst=DEST_IP) /
            TCP(sport=sport, dport=dport, flags="FA", seq=seq_s, ack=seq_d, window=65535),
            _ts(t)
        )
        t += 0.005; seq_s += 1
        fin_d = (
            Ether(src=DEST_MAC, dst=SOURCE_MAC) /
            IP(src=DEST_IP, dst=SOURCE_IP) /
            TCP(sport=dport, dport=sport, flags="FA", seq=seq_d, ack=seq_s, window=65535),
            _ts(t)
        )
        t += 0.005; seq_d += 1
        fin_ack = (
            Ether(src=SOURCE_MAC, dst=DEST_MAC) /
            IP(src=SOURCE_IP, dst=DEST_IP) /
            TCP(sport=sport, dport=dport, flags="A", seq=seq_s, ack=seq_d, window=65535),
            _ts(t)
        )
        t += 0.010

        stream = [syn, synack, ack] + data_pkts + [data_ack, fin_s, fin_d, fin_ack]

        # Clean path: both source and dest see all packets
        src_pkts.extend(stream)
        dst_pkts.extend(stream)

    _write_pair("clean_path", src_pkts, dst_pkts)


# ---------------------------------------------------------------------------
# Scenario 2 — SYN Block (Full Firewall Block)
# Firewall drops all SYNs before they reach the destination.
# Source: sends SYNs, retransmits, eventually gives up.
# Dest: sees nothing (zero flows).
# Expected verdict: FULL DROP, HIGH confidence.
# ---------------------------------------------------------------------------

def gen_syn_block() -> None:
    """Firewall drops all SYNs. Destination receives nothing."""
    src_pkts: list[tuple] = []
    dst_pkts: list[tuple] = []  # stays empty

    t = 0.0
    for stream_num in range(4):
        sport = 51000 + stream_num
        dport = 443
        seq = 3000 + stream_num * 100
        t += stream_num * 1.5

        # SYN — source sends, never gets SYN-ACK
        for attempt in range(3):  # 3 SYN attempts (original + 2 retransmits)
            syn = (
                Ether(src=SOURCE_MAC, dst=FW_MAC) /
                IP(src=SOURCE_IP, dst=DEST_IP) /
                TCP(sport=sport, dport=dport, flags="S", seq=seq, window=65535),
                _ts(t)
            )
            src_pkts.append(syn)
            # Retransmit backoff: 1s, 3s
            t += 1.0 * (2 ** attempt)

        # Dest sees nothing — SYNs were dropped silently by firewall

    _write_pair("syn_block", src_pkts, dst_pkts)


# ---------------------------------------------------------------------------
# Scenario 3 — Partial Drop (Mid-stream Packet Loss)
# One TCP stream delivers fully. A second stream loses ~40% of packets.
# Source: shows retransmissions for the dropped segments.
# Dest: receives only the segments that made it through.
# Expected verdict: PARTIAL DROP, MEDIUM-HIGH confidence.
# ---------------------------------------------------------------------------

def gen_partial_drop() -> None:
    """40% packet loss on stream 2. Stream 1 is clean."""
    src_pkts: list[tuple] = []
    dst_pkts: list[tuple] = []

    # Stream 1 — clean, delivered fully
    t = 0.0
    sport1, dport1 = 52001, 80
    seq_s1, seq_d1 = 1000, 2000

    def add_both(pkt_ts: tuple) -> None:
        src_pkts.append(pkt_ts)
        dst_pkts.append(pkt_ts)

    def add_src_only(pkt_ts: tuple) -> None:
        src_pkts.append(pkt_ts)
        # dest does NOT see this packet

    # Handshake stream 1 (clean)
    syn1 = (Ether(src=SOURCE_MAC, dst=DEST_MAC) / IP(src=SOURCE_IP, dst=DEST_IP) /
            TCP(sport=sport1, dport=dport1, flags="S", seq=seq_s1, window=65535), _ts(t))
    add_both(syn1); t += 0.010; seq_s1 += 1

    sa1 = (Ether(src=DEST_MAC, dst=SOURCE_MAC) / IP(src=DEST_IP, dst=SOURCE_IP) /
           TCP(sport=dport1, dport=sport1, flags="SA", seq=seq_d1, ack=seq_s1, window=65535), _ts(t))
    add_both(sa1); t += 0.010; seq_d1 += 1

    ack1 = (Ether(src=SOURCE_MAC, dst=DEST_MAC) / IP(src=SOURCE_IP, dst=DEST_IP) /
            TCP(sport=sport1, dport=dport1, flags="A", seq=seq_s1, ack=seq_d1, window=65535), _ts(t))
    add_both(ack1); t += 0.005

    for i in range(8):
        payload = f"data-stream1-seg{i}".encode()
        d = (Ether(src=SOURCE_MAC, dst=DEST_MAC) / IP(src=SOURCE_IP, dst=DEST_IP) /
             TCP(sport=sport1, dport=dport1, flags="A", seq=seq_s1, ack=seq_d1, window=65535) /
             Raw(load=payload), _ts(t))
        add_both(d); t += 0.005; seq_s1 += len(payload)

    da1 = (Ether(src=DEST_MAC, dst=SOURCE_MAC) / IP(src=DEST_IP, dst=SOURCE_IP) /
           TCP(sport=dport1, dport=sport1, flags="A", seq=seq_d1, ack=seq_s1, window=65535), _ts(t))
    add_both(da1); t += 0.010

    # Stream 2 — partial drop (drop segments 2, 4, 6 out of 8)
    t = 3.0
    sport2, dport2 = 52002, 8080
    seq_s2, seq_d2 = 5000, 6000
    dropped_segments = {2, 4, 6}

    syn2 = (Ether(src=SOURCE_MAC, dst=DEST_MAC) / IP(src=SOURCE_IP, dst=DEST_IP) /
            TCP(sport=sport2, dport=dport2, flags="S", seq=seq_s2, window=65535), _ts(t))
    add_both(syn2); t += 0.010; seq_s2 += 1

    sa2 = (Ether(src=DEST_MAC, dst=SOURCE_MAC) / IP(src=DEST_IP, dst=SOURCE_IP) /
           TCP(sport=dport2, dport=sport2, flags="SA", seq=seq_d2, ack=seq_s2, window=65535), _ts(t))
    add_both(sa2); t += 0.010; seq_d2 += 1

    ack2 = (Ether(src=SOURCE_MAC, dst=DEST_MAC) / IP(src=SOURCE_IP, dst=DEST_IP) /
            TCP(sport=sport2, dport=dport2, flags="A", seq=seq_s2, ack=seq_d2, window=65535), _ts(t))
    add_both(ack2); t += 0.005

    for i in range(8):
        payload = f"data-stream2-seg{i}".encode()
        d = (Ether(src=SOURCE_MAC, dst=DEST_MAC) / IP(src=SOURCE_IP, dst=DEST_IP) /
             TCP(sport=sport2, dport=dport2, flags="A", seq=seq_s2, ack=seq_d2, window=65535) /
             Raw(load=payload), _ts(t))
        if i in dropped_segments:
            add_src_only(d)   # source sent it; dest never sees it
            t += 0.005

            # Source retransmits after timeout
            retrans = (Ether(src=SOURCE_MAC, dst=DEST_MAC) / IP(src=SOURCE_IP, dst=DEST_IP) /
                       TCP(sport=sport2, dport=dport2, flags="A", seq=seq_s2, ack=seq_d2, window=65535) /
                       Raw(load=payload), _ts(t + 0.200))
            add_src_only(retrans)  # retransmit also dropped
            t += 0.250
        else:
            add_both(d)
            t += 0.005
        seq_s2 += len(payload)

    _write_pair("partial_drop", src_pkts, dst_pkts)


# ---------------------------------------------------------------------------
# Scenario 4 — ICMP Reject (Firewall Actively Rejects)
# Firewall sends ICMP Admin Prohibited back to source.
# Source: sees SYNs go out + ICMP Admin Prohibited responses from firewall.
# Dest: sees nothing.
# Expected verdict: FULL DROP, HIGH confidence. Source sees ICMP rejection.
# ---------------------------------------------------------------------------

def gen_icmp_reject() -> None:
    """Firewall rejects traffic with ICMP Admin Prohibited (code 13)."""
    src_pkts: list[tuple] = []
    dst_pkts: list[tuple] = []  # stays empty

    t = 0.0
    for stream_num in range(3):
        sport = 53000 + stream_num
        dport = 22   # SSH — common firewall block target
        seq = 7000 + stream_num * 100
        t += stream_num * 0.5

        # Source sends SYN
        syn = (
            Ether(src=SOURCE_MAC, dst=FW_MAC) /
            IP(src=SOURCE_IP, dst=DEST_IP) /
            TCP(sport=sport, dport=dport, flags="S", seq=seq, window=65535),
            _ts(t)
        )
        src_pkts.append(syn)
        t += 0.010

        # Firewall sends ICMP Admin Prohibited (Type 3, Code 13) back to source
        icmp_reject = (
            Ether(src=FW_MAC, dst=SOURCE_MAC) /
            IP(src=FIREWALL_IP, dst=SOURCE_IP) /
            ICMP(type=3, code=13) /
            IP(src=SOURCE_IP, dst=DEST_IP) /
            TCP(sport=sport, dport=dport, flags="S", seq=seq),
            _ts(t)
        )
        src_pkts.append(icmp_reject)
        t += 0.010

    # Some DNS queries that also get rejected
    for q_num in range(2):
        t += q_num * 0.3
        dns_query = (
            Ether(src=SOURCE_MAC, dst=FW_MAC) /
            IP(src=SOURCE_IP, dst=DEST_IP) /
            UDP(sport=12000 + q_num, dport=53) /
            DNS(rd=1, qd=DNSQR(qname=f"internal-{q_num}.corp")),
            _ts(t)
        )
        src_pkts.append(dns_query)
        t += 0.010

        icmp_dns_reject = (
            Ether(src=FW_MAC, dst=SOURCE_MAC) /
            IP(src=FIREWALL_IP, dst=SOURCE_IP) /
            ICMP(type=3, code=13) /
            IP(src=SOURCE_IP, dst=DEST_IP) /
            UDP(sport=12000 + q_num, dport=53),
            _ts(t)
        )
        src_pkts.append(icmp_dns_reject)
        t += 0.010

    _write_pair("icmp_reject", src_pkts, dst_pkts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Generating endpoint-correlation pcap pairs → {OUTPUT_DIR}/\n")

    print("1/4 clean_path")
    gen_clean_path()

    print("2/4 syn_block")
    gen_syn_block()

    print("3/4 partial_drop")
    gen_partial_drop()

    print("4/4 icmp_reject")
    gen_icmp_reject()

    print(f"\nDone. 8 pcap files written to {OUTPUT_DIR}/")
    print("\nTest commands (run from Claude Code):")
    print(f"  /pcap-forensics {OUTPUT_DIR}/clean_path_source.pcap --compare {OUTPUT_DIR}/clean_path_dest.pcap --mode endpoint-correlation")
    print(f"  /pcap-forensics {OUTPUT_DIR}/syn_block_source.pcap --compare {OUTPUT_DIR}/syn_block_dest.pcap --mode endpoint-correlation")
    print(f"  /pcap-forensics {OUTPUT_DIR}/partial_drop_source.pcap --compare {OUTPUT_DIR}/partial_drop_dest.pcap --mode endpoint-correlation")
    print(f"  /pcap-forensics {OUTPUT_DIR}/icmp_reject_source.pcap --compare {OUTPUT_DIR}/icmp_reject_dest.pcap --mode endpoint-correlation")
