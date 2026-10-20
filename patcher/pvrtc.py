"""Pure-Python PVRTC 4bpp decoder and PNG writer (no dependencies).

The APK ships 180 textures only as `.ddspvr`: a DDS header (FourCC `PVR4` = RGBA, `PVR3` = RGB)
around PVRTC 4bpp data, which only PowerVR GPUs can sample. On other GPUs the engine asks for a
`.png` of the same name that the original server used to provide, so the patcher decodes them.

Decoding follows the PVRTC 4bpp scheme: 64-bit blocks of 4x4 pixels in Morton (twiddled) order,
each with 2-bit modulation per pixel and two low-res colours that are bilinearly upscaled.
"""
import struct
import zlib


def _color_a(c):
    if c & 0x8000:  # opaque RGB 5:5:4
        return ((c >> 10) & 0x1f, (c >> 5) & 0x1f, (c & 0x1e) | ((c & 0x1e) >> 4), 0xf)
    return (((c >> 7) & 0x1e) | ((c >> 11) & 1), ((c >> 3) & 0x1e) | ((c >> 7) & 1),
            ((c << 1) & 0x1c) | ((c >> 2) & 3), (c >> 11) & 0xe)


def _color_b(c):
    if c & 0x80000000:  # opaque RGB 5:5:5
        return ((c >> 26) & 0x1f, (c >> 21) & 0x1f, (c >> 16) & 0x1f, 0xf)
    return (((c >> 23) & 0x1e) | ((c >> 27) & 1), ((c >> 19) & 0x1e) | ((c >> 23) & 1),
            ((c >> 15) & 0x1e) | ((c >> 19) & 1), (c >> 27) & 0xe)


def _morton(x, y, bits):
    v = 0
    for i in range(bits):
        v |= ((y >> i) & 1) << (2 * i) | ((x >> i) & 1) << (2 * i + 1)
    return v


def decode(data, width, height):
    """Returns RGBA bytes (row-major, top row first) for PVRTC 4bpp `data`."""
    bw, bh = max(width // 4, 2), max(height // 4, 2)
    bits = (min(bw, bh) - 1).bit_length()
    blocks = []
    for by in range(bh):
        row = []
        for bx in range(bw):
            # Morton order over the square part, then linear across extra squares (rectangles)
            m = _morton(bx % (1 << bits), by % (1 << bits), bits)
            m += ((bx >> bits) + (by >> bits)) << (2 * bits)
            mod, col = struct.unpack_from('<II', data, m * 8)
            row.append((mod, col & 1, _color_a(col & 0xffff), _color_b(col)))
        blocks.append(row)

    out = bytearray(width * height * 4)
    weights = ((0, 3, 5, 8), (0, 4, 4, 8))  # standard / punch-through modulation, in eighths
    for y in range(height):
        yy = y - 2
        by0, v = (yy >> 2) % bh, yy & 3
        by1 = (by0 + 1) % bh
        for x in range(width):
            xx = x - 2
            bx0, u = (xx >> 2) % bw, xx & 3
            bx1 = (bx0 + 1) % bw
            p, q, r, s = blocks[by0][bx0], blocks[by0][bx1], blocks[by1][bx0], blocks[by1][bx1]
            wp, wq, wr, ws = (4 - u) * (4 - v), u * (4 - v), (4 - u) * v, u * v
            a = [p[2][k] * wp + q[2][k] * wq + r[2][k] * wr + s[2][k] * ws for k in range(4)]
            b = [p[3][k] * wp + q[3][k] * wq + r[3][k] * wr + s[3][k] * ws for k in range(4)]
            own = blocks[y >> 2][x >> 2]
            code = (own[0] >> (2 * ((y & 3) * 4 + (x & 3)))) & 3
            w = weights[own[1]][code]
            o = (y * width + x) * 4
            for k in range(3):  # 5-bit channels scaled by 16 → 8 bit
                c = (a[k] * (8 - w) + b[k] * w) / 8.0
                out[o + k] = min(255, int(c * 255 / (31 * 16) + 0.5))
            alpha = (a[3] * (8 - w) + b[3] * w) / 8.0
            out[o + 3] = 0 if (own[1] and code == 2) else min(255, int(alpha * 255 / (15 * 16) + 0.5))
    return bytes(out)


def ddspvr_to_rgba(blob):
    """Parses a .ddspvr file; returns (width, height, rgba bytes, has_alpha) for mip level 0."""
    if blob[:4] != b'DDS ':
        raise ValueError('not a DDS file')
    height, width = struct.unpack_from('<II', blob, 12)
    fourcc = blob[84:88]
    if fourcc not in (b'PVR4', b'PVR3'):
        raise ValueError('unsupported FourCC %r' % fourcc)
    return width, height, decode(blob[128:], width, height), fourcc == b'PVR4'


def png(width, height, rgba, alpha=True):
    """Encodes RGBA (or drops alpha) as a PNG file."""
    stride = width * 4
    if alpha:
        raw = b''.join(b'\0' + rgba[y * stride:(y + 1) * stride] for y in range(height))
        ctype = 6
    else:
        rgb = bytearray()
        for y in range(height):
            rgb += b'\0'
            row = rgba[y * stride:(y + 1) * stride]
            for x in range(0, stride, 4):
                rgb += row[x:x + 3]
        raw, ctype = bytes(rgb), 2

    def chunk(kind, body):
        return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, ctype, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))
