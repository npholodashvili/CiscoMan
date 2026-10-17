"""Minimal SNMPv2c GET over UDP — no pysnmp, freezes cleanly under PyInstaller.

Encodes/decodes enough BER for sysDescr / sysName / sysObjectID.
"""

from __future__ import annotations

import random
import socket
from typing import Optional


def _encode_length(n: int) -> bytes:
    if n < 0x80:
        return bytes([n])
    body = n.to_bytes((n.bit_length() + 7) // 8 or 1, "big")
    return bytes([0x80 | len(body)]) + body


def _encode_int(n: int) -> bytes:
    if n == 0:
        body = b"\x00"
    else:
        length = max(1, (n.bit_length() + 8) // 8)
        body = n.to_bytes(length, "big", signed=True)
        # trim leftover sign-extension bytes
        while len(body) > 1 and (
            (body[0] == 0 and body[1] < 0x80) or (body[0] == 0xFF and body[1] >= 0x80)
        ):
            body = body[1:]
    return b"\x02" + _encode_length(len(body)) + body


def _encode_octet(data: bytes) -> bytes:
    return b"\x04" + _encode_length(len(data)) + data


def _encode_null() -> bytes:
    return b"\x05\x00"


def _encode_oid(oid: str) -> bytes:
    parts = [int(p) for p in oid.strip(".").split(".") if p != ""]
    if len(parts) < 2:
        raise ValueError(f"OID too short: {oid}")
    out = [40 * parts[0] + parts[1]]
    for p in parts[2:]:
        if p < 0:
            raise ValueError("negative OID arc")
        if p < 128:
            out.append(p)
            continue
        stack = [p & 0x7F]
        p >>= 7
        while p:
            stack.append(0x80 | (p & 0x7F))
            p >>= 7
        out.extend(reversed(stack))
    body = bytes(out)
    return b"\x06" + _encode_length(len(body)) + body


def _tlv(tag: int, *parts: bytes) -> bytes:
    body = b"".join(parts)
    return bytes([tag]) + _encode_length(len(body)) + body


def encode_get_request(community: str, oids: list[str], request_id: Optional[int] = None) -> bytes:
    """Build a SNMPv2c GetRequest packet."""
    rid = request_id if request_id is not None else random.randint(1, 0x7FFFFFFF)
    varbinds = [_tlv(0x30, _encode_oid(oid), _encode_null()) for oid in oids]
    pdu = _tlv(0xA0, _encode_int(rid), _encode_int(0), _encode_int(0), _tlv(0x30, *varbinds))
    return _tlv(0x30, _encode_int(1), _encode_octet(community.encode("latin-1")), pdu)


def encode_get_response(
    community: str,
    bindings: dict[str, str],
    request_id: int = 1,
) -> bytes:
    """Build a SNMPv2c GetResponse (used by selftest / unit tests)."""
    varbinds = [
        _tlv(0x30, _encode_oid(oid), _encode_octet(val.encode("utf-8")))
        for oid, val in bindings.items()
    ]
    pdu = _tlv(0xA2, _encode_int(request_id), _encode_int(0), _encode_int(0), _tlv(0x30, *varbinds))
    return _tlv(0x30, _encode_int(1), _encode_octet(community.encode("latin-1")), pdu)


def _read_length(buf: bytes, i: int) -> tuple[int, int]:
    first = buf[i]
    i += 1
    if first < 0x80:
        return first, i
    n = first & 0x7F
    val = int.from_bytes(buf[i : i + n], "big")
    return val, i + n


def _expect(buf: bytes, i: int, tag: Optional[int] = None) -> tuple[int, int, int]:
    """Return (tag, content_start, content_end) and do not advance past content."""
    got = buf[i]
    i += 1
    if tag is not None and got != tag:
        raise ValueError(f"expected tag {tag:#x}, got {got:#x}")
    length, i = _read_length(buf, i)
    return got, i, i + length


def _decode_int(buf: bytes, start: int, end: int) -> int:
    return int.from_bytes(buf[start:end], "big", signed=True)


def _decode_oid(buf: bytes, start: int, end: int) -> str:
    if start >= end:
        return ""
    first = buf[start]
    arcs = [first // 40, first % 40]
    n = 0
    for b in buf[start + 1 : end]:
        n = (n << 7) | (b & 0x7F)
        if b < 0x80:
            arcs.append(n)
            n = 0
    return ".".join(str(a) for a in arcs)


def decode_get_response(packet: bytes) -> dict[str, str]:
    """Parse SNMPv2c GetResponse into {oid: value_string}."""
    tag, i, end = _expect(packet, 0, 0x30)
    # version
    _, vs, ve = _expect(packet, i, 0x02)
    i = ve
    # community
    _, cs, ce = _expect(packet, i, 0x04)
    i = ce
    # PDU (GetResponse 0xA2, or Report 0xA8, or GetRequest echo)
    pdu_tag, ps, pe = _expect(packet, i)
    i = ps
    # request-id, err-status, err-index
    for _ in range(3):
        _, s, e = _expect(packet, i, 0x02)
        i = e
    # varbind list
    _, vs, ve = _expect(packet, i, 0x30)
    i = vs
    result: dict[str, str] = {}
    while i < ve:
        _, bs, be = _expect(packet, i, 0x30)
        j = bs
        _, os_, oe = _expect(packet, j, 0x06)
        oid = _decode_oid(packet, os_, oe)
        j = oe
        vtag, vs2, ve2 = _expect(packet, j)
        result[oid] = _decode_value(vtag, packet[vs2:ve2])
        i = be
    return result


def _decode_value(tag: int, content: bytes) -> str:
    if tag == 0x04:  # OCTET STRING
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return content.decode("latin-1", errors="replace")
    if tag == 0x06:  # OID
        return _oid_from_body(content)
    if tag in (0x02, 0x41, 0x42, 0x43, 0x46):  # int / counters / gauge / ticks
        return str(int.from_bytes(content, "big", signed=(tag == 0x02)))
    if tag == 0x05:
        return ""
    return content.hex()


def _oid_from_body(content: bytes) -> str:
    if not content:
        return ""
    first = content[0]
    arcs = [first // 40, first % 40]
    n = 0
    for b in content[1:]:
        n = (n << 7) | (b & 0x7F)
        if b < 0x80:
            arcs.append(n)
            n = 0
    return ".".join(str(a) for a in arcs)


def snmp_get(
    ip: str,
    community: str,
    oids: list[str],
    timeout: float = 2.0,
    port: int = 161,
) -> dict[str, str]:
    """Send one GetRequest and return decoded bindings (empty dict on timeout/error)."""
    packet = encode_get_request(community, oids)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(timeout)
        sock.sendto(packet, (ip, port))
        data, _addr = sock.recvfrom(4096)
    except OSError:
        return {}
    finally:
        sock.close()
    try:
        return decode_get_response(data)
    except Exception:
        return {}


def bindings_ok() -> bool:
    """Encode/decode round-trip used by --selftest."""
    pkt = encode_get_request("public", ["1.3.6.1.2.1.1.1.0", "1.3.6.1.2.1.1.5.0"], request_id=7)
    if pkt[0] != 0x30 or b"public" not in pkt:
        return False
    resp = encode_get_response(
        "public",
        {
            "1.3.6.1.2.1.1.1.0": "Cisco IOS Software, C2960X",
            "1.3.6.1.2.1.1.5.0": "SW-CORE-01",
            "1.3.6.1.2.1.1.2.0": "1.3.6.1.4.1.9.1.1208",
        },
        request_id=7,
    )
    decoded = decode_get_response(resp)
    return (
        decoded.get("1.3.6.1.2.1.1.5.0") == "SW-CORE-01"
        and "Cisco" in decoded.get("1.3.6.1.2.1.1.1.0", "")
    )
