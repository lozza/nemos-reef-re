"""Reads the entity list of a Nemo's Reef .iscn scene file (sdr::til::IsoSceneLoader, big-endian).

The client only loads level_no_entities.iscn; level.iscn in the APK holds the designed starting
layout (Nemo's anemone, coral fans, scenery), which the original server sent to new players as their
own world entities. This parser returns those entities.
"""
import struct


class _Reader:
    def __init__(self, d):
        self.d, self.p = d, 0

    def take(self, fmt):
        v = struct.unpack_from('>' + fmt, self.d, self.p)
        self.p += struct.calcsize('>' + fmt)
        return v if len(v) > 1 else v[0]

    def str(self):
        n = self.take('H')
        s = self.d[self.p:self.p + n].decode('utf-8', 'replace')
        self.p += n
        return s


def entities(data):
    """[{name, ipro, x, z, mirror}] in scene order."""
    if data[2:10] != b'Iscn 0.2':
        raise ValueError('not an Iscn 0.2 scene')
    r = _Reader(data)
    r.p = 12
    r.str()                                  # tileset
    w, h = r.take('ii')
    r.p += 3 * 4 * w * h                     # tile index, attribute and tile-data-list grids
    r.take('H')
    for _ in range(r.take('H')):             # tile-data lists
        n = r.take('H')
        r.p += 4 * n
        r.take('H')
    out = []
    for _ in range(r.take('H')):
        e = {'name': r.str(), 'ipro': r.str(), 'x': 0, 'z': 0, 'mirror': False}
        for _ in range(r.take('H')):
            kind = r.take('B')
            if kind == 0:
                r.take('fff')                # free position (unused for tile entities)
            elif kind == 1:
                e['x'], _y, e['z'] = r.take('iii')
            elif kind == 2:
                e['mirror'] = bool(r.take('B'))
            elif kind == 3:
                r.take('b')                  # layer
            else:
                raise ValueError('unknown entity attribute %d' % kind)
        out.append(e)
    return out
