# usage: python3 -I dis.py <lib.so> <symbol-substring> [maxbytes]
import sys, lief, capstone, subprocess
lib = lief.parse(sys.argv[1]); pat = sys.argv[2]; mx = int(sys.argv[3]) if len(sys.argv) > 3 else 4000
syms = {}
for s in list(lib.dynamic_symbols) + list(lib.symtab_symbols):
    if s.value and s.name: syms[s.value & ~1] = s
byaddr = sorted(syms)
def name(a):
    s = syms.get(a & ~1); return s and subprocess.run(['c++filt', s.name], capture_output=True, text=True).stdout.strip()
# literal / string resolution helpers
def rd(addr, n):
    try: return bytes(lib.get_content_from_virtual_address(addr, n))
    except Exception: return b''
def cstr(addr):
    b = rd(addr, 200); i = b.find(b'\0')
    s = b[:i] if i >= 0 else b
    return s.decode('latin1') if len(s) >= 2 and all(32 <= c < 127 for c in s) else None
targets = [s for s in syms.values() if pat in s.name or pat in (name(s.value) or '')]
for s in targets[:6]:
    a = s.value; thumb = a & 1; a &= ~1
    size = s.size or mx
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB if thumb else capstone.CS_MODE_ARM)
    print(f'==== {name(a)} @ {a:#x} size {size} {"thumb" if thumb else "arm"}')
    code = rd(a, min(size, mx))
    for ins in md.disasm(code, a):
        extra = ''
        if ins.mnemonic.startswith('b') and ins.op_str.startswith('#'):
            t = int(ins.op_str[1:], 16); n = name(t) or name(t | 1)
            if n: extra = '  ; ' + n
        if ins.mnemonic == 'ldr' and '[pc' in ins.op_str:
            try:
                off = int(ins.op_str.split('#')[-1].rstrip(']'), 16) if '#' in ins.op_str else 0
                pc = (ins.address + (4 if thumb else 8)) & ~3
                v = int.from_bytes(rd(pc + off, 4), 'little'); extra = f'  ; ={v:#x}'
            except Exception: pass
        print(f'{ins.address:08x}  {ins.mnemonic:8} {ins.op_str}{extra}')
