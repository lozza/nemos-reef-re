# Replaces Ghidra PIC expressions like (DAT_00750e24 + 0x750ce6) with the string they point to.
# usage: python3 -I resolve.py <lib.so> <decomp-dir> <out-dir>
import sys, os, re, lief
lib = lief.parse(sys.argv[1])
BASE = 0x10000
def rd(a, n):
    a -= BASE
    try: return bytes(lib.get_content_from_virtual_address(a, n))
    except Exception: return b''
def cstr(a):
    b = rd(a, 300); i = b.find(b'\0')
    if i < 1: return None
    s = b[:i]
    if not all(32 <= c < 127 or c in (9, 10) for c in s): return None
    return s.decode('latin1')
pat = re.compile(r'\(?\*?\(?(?:\([^()]*\))?\s*(?:&?(DAT|UNK)_([0-9a-f]{8}))\s*\+\s*(?:&?(?:DAT|UNK)_([0-9a-f]{8})|(0x[0-9a-f]+))\)?')
def sub(m):
    a = int(m.group(2), 16)
    if m.group(3):  # &UNK_x + DAT_y : one is the PC anchor, the other holds the offset
        b = int(m.group(3), 16)
        cands = [b + int.from_bytes(rd(a, 4), 'little'), a + int.from_bytes(rd(b, 4), 'little')]
    else:
        cands = [int.from_bytes(rd(a, 4), 'little') + int(m.group(4), 16)]
    for t in cands:
        for tt in (t & 0xffffffff,):
            s = cstr(tt)
            if s is not None: return m.group(0) + f'/*"{s}"*/'
            p = int.from_bytes(rd(tt, 4), 'little')  # may be a pointer to a string (GOT)
            s = cstr(p + BASE)
            if s is not None: return m.group(0) + f'/*->"{s}"*/'
    return m.group(0)
import json
gmap = {int(k, 16): v for k, v in json.load(open('/home/user/nemos-reef/re/gstrings_emu.json')).items() if 0xc31000 <= int(k, 16) < 0xfd6000}
_old_sub = sub
def sub(m):
    a = int(m.group(2), 16)
    cands = []
    if m.group(3):
        b = int(m.group(3), 16)
        cands = [b + int.from_bytes(rd(a, 4), 'little') - BASE, a + int.from_bytes(rd(b, 4), 'little') - BASE]
    else:
        cands = [int.from_bytes(rd(a, 4), 'little') + int(m.group(4), 16) - BASE]
    for t in cands:
        for d in range(0, 0x100, 4):  # Ghidra often folds a field offset in later; try the base itself first
            if (t + d) in gmap and d == 0: return m.group(0) + f'/*[{gmap[t]}]*/'
    return _old_sub(m)
src, dst = sys.argv[2], sys.argv[3]
os.makedirs(dst, exist_ok=True)
for f in os.listdir(src):
    t = open(os.path.join(src, f)).read()
    open(os.path.join(dst, f), 'w').write(pat.sub(sub, t))
