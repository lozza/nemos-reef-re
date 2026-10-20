# Builds {global String object address: literal} from String-constructor calls in calls.json,
# then writes an annotated call listing: for each call, args shown as "literal" or [global "literal"].
import sys, json, lief, subprocess
lib = lief.parse(sys.argv[1]); d = json.load(open(sys.argv[2]))
funcs = {int(k, 16): v for k, v in d['funcs'].items()}
def rd(a, n):
    try: return bytes(lib.get_content_from_virtual_address(a, n))
    except Exception: return b''
def cstr(a):
    b = rd(a, 400); i = b.find(b'\0')
    if i < 1: return None
    s = b[:i]
    return s.decode('latin1') if all(32 <= c < 127 or c in (9, 10, 13) for c in s) else None
names = sorted(set(funcs.values()))
dem = dict(zip(names, subprocess.run(['c++filt'], input='\n'.join(names), capture_output=True, text=True).stdout.split('\n')))
import capstone
_arm = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
def thunk(a):
    ins = list(_arm.disasm(rd(a, 12), a))
    if len(ins) >= 2 and ins[0].mnemonic == 'ldr' and ins[0].op_str.startswith('ip, [pc') and ins[1].mnemonic == 'add':
        disp = int(ins[0].op_str.split('#')[1].rstrip(']'), 16) if '#' in ins[0].op_str else 0
        v = int.from_bytes(rd(a + 8 + disp, 4), 'little')
        return (a + 12 + v) & 0xffffffff
def fn(a):
    if a == 0xFFFFFFFE: return 'VIRTUAL'
    n = dem.get(funcs.get(a & ~1, ''))
    if n: return n
    t = thunk(a & ~1)
    if t is not None:
        n = dem.get(funcs.get(t & ~1, ''))
        if n: return n
        # thunk into PLT
        return f'thunk->{t:#x}'
    return hex(a)
ctors = {a for a, n in funcs.items() if dem.get(n, '').startswith('sdr::String::String(char const*')} | {0x5698c8}
gmap = {}
for site, tgt, regs, f in d['calls']:
    regs = {int(k): v for k, v in regs.items()}
    if (tgt & ~1) in ctors and 0 in regs and 1 in regs:
        s = cstr(regs[1])
        if s is not None: gmap.setdefault(regs[0], s)
emu = json.load(open(sys.argv[5]))
for k, v in emu.items():
    a = int(k, 16)
    if 0xc31000 <= a < 0xfd6000: gmap[a] = v
print(len(gmap), 'global strings', file=sys.stderr)
json.dump({hex(k): v for k, v in gmap.items()}, open(sys.argv[3], 'w'), indent=0)
with open(sys.argv[4], 'w') as out:
    for site, tgt, regs, f in d['calls']:
        regs = {int(k): v for k, v in regs.items()}
        args = []
        for i, v in sorted(regs.items()):
            if v in gmap: args.append(f'r{i}=[{gmap[v]!r}]')
            elif cstr(v) is not None: args.append(f'r{i}={cstr(v)!r}')
            else:
                p = int.from_bytes(rd(v, 4), 'little')  # pointer-to-string (GOT)
                if p in gmap: args.append(f'r{i}=*[{gmap[p]!r}]')
                elif cstr(p) is not None: args.append(f'r{i}=*{cstr(p)!r}')
        out.write(f'{site:08x}\t{fn(f)}\t-> {fn(tgt)}\t{" ".join(args)}\n')
