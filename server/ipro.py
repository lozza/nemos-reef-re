"""Reader for the attribute block of the game's .ipro prototype files (assets/prototypes/*.ipro).

Attributes are stored as: u16 key length, key, 0x00 0x01, type byte, value, where type 1 = int32,
2 = float32, 3 = u16-length string (all big-endian).
"""
import re
import struct

_ATTR = re.compile(rb'\x00([\x01-\x40])([A-Za-z_][A-Za-z0-9_]*)\x00\x01([\x01\x02\x03])')


def read_attributes(data):
    attrs = {}
    for m in _ATTR.finditer(data):
        n, key, kind = m.group(1)[0], m.group(2), m.group(3)[0]
        if len(key) != n:
            continue
        p = m.end()
        if kind == 1:
            attrs[key.decode()] = struct.unpack('>i', data[p:p + 4])[0]
        elif kind == 2:
            attrs[key.decode()] = round(struct.unpack('>f', data[p:p + 4])[0], 4)
        else:
            ln = struct.unpack('>H', data[p:p + 2])[0]
            attrs[key.decode()] = data[p + 2:p + 2 + ln].decode('utf-8', 'replace')
    return attrs
