# Emulates every .init_array constructor in libsdr.so with Unicorn, hooking the PLT/thunk
# String constructors, and records {global String object: literal}.
import sys, json, lief
from unicorn import *
from unicorn.arm_const import *
lib = lief.parse(sys.argv[1])
mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
TOP = 0x1000000
mu.mem_map(0, TOP)
for seg in lib.segments:
    if seg.type == lief.ELF.Segment.TYPE.LOAD:
        mu.mem_write(seg.virtual_address, bytes(seg.content))
for r in lib.dynamic_relocations:  # ARM_RELATIVE already holds the target in-place (base 0)
    pass
STACK, SSZ = 0x2000000, 0x100000
mu.mem_map(STACK, SSZ)
HEAP = 0x3000000; mu.mem_map(HEAP, 0x1000000); heap = [HEAP]
RET = 0x4000000; mu.mem_map(RET, 0x1000); mu.mem_write(RET, b'\x00\xbf' * 0x800)
def cstr(a):
    b = mu.mem_read(a, 300); i = b.find(b'\0'); return bytes(b[:i]).decode('latin1')
# map PLT entries -> imported names so we can stub them
plt = lib.get_section('.plt')
slots = {r.address: r.symbol.name for r in lib.pltgot_relocations if r.has_symbol}
import capstone
arm = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM); pd = bytes(plt.content); pltname = {}
for i in range(20, len(pd), 12):
    ins = list(arm.disasm(pd[i:i + 12], plt.virtual_address + i))
    if len(ins) == 3:
        try:
            imms = [int(x.op_str.split('#')[-1].rstrip(']!'), 16) for x in ins]
            got = plt.virtual_address + i + 8 + sum(imms)
            if got in slots: pltname[plt.virtual_address + i] = slots[got]
        except Exception: pass
# thunks (ldr ip,[pc]; add ip,pc,ip; bx ip) in .text resolve to a real function: follow them
syms = {}
for s in list(lib.symtab_symbols) + list(lib.dynamic_symbols):
    if s.value and s.name: syms[s.value & ~1] = s.name
import subprocess
ctor_names = {n for n in set(syms.values()) if n.startswith('_ZN3sdr6StringC')}
dem = dict(zip(sorted(ctor_names), subprocess.run(['c++filt'], input='\n'.join(sorted(ctor_names)), capture_output=True, text=True).stdout.split('\n')))
CHAR_CTORS = {a for a, n in syms.items() if n in dem and 'char const*' in dem[n]}
COPY_CTORS = {a for a, n in syms.items() if n in dem and 'String const&' in dem[n]}
found = {}
def resolve_thunk(a):
    a &= ~1
    try:
        ins = list(arm.disasm(bytes(mu.mem_read(a, 12)), a))
        if len(ins) >= 2 and ins[0].mnemonic == 'ldr' and ins[1].mnemonic == 'add' and 'pc' in ins[1].op_str:
            off = int.from_bytes(mu.mem_read(a + 8 + int(ins[0].op_str.split('#')[-1].rstrip(']') if '#' in ins[0].op_str else '0', 16), 4), 'little')
            return (a + 12 + off) & 0xffffffff if ins[1].op_str.startswith('pc') else (a + 12 + off) & 0xffffffff
    except Exception: pass
    return None
def strval(obj):  # read back an sdr::String's char* (we lay it out as [vtbl, ptr])
    return found.get(obj)
def ret(uc):
    lr = uc.reg_read(UC_ARM_REG_LR)
    uc.reg_write(UC_ARM_REG_PC, lr)
def hook_code(uc, addr, size, ud):
    tgt = addr
    t = resolve_thunk(addr)
    if t is not None: tgt = t & ~1
    if tgt in CHAR_CTORS:
        this, s = uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1)
        try: found[this] = cstr(s)
        except Exception: pass
        uc.reg_write(UC_ARM_REG_R0, this); ret(uc); return
    if tgt in COPY_CTORS:
        this, other = uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1)
        if other in found: found[this] = found[other]
        uc.reg_write(UC_ARM_REG_R0, this); ret(uc); return
    if addr in pltname or (plt.virtual_address <= addr < plt.virtual_address + plt.size):
        n = pltname.get(addr, '')
        if n in ('malloc', '_Znwj', '_Znaj', 'operator new'):
            sz = (uc.reg_read(UC_ARM_REG_R0) + 15) & ~15; uc.reg_write(UC_ARM_REG_R0, heap[0]); heap[0] += max(sz, 16)
        else:
            uc.reg_write(UC_ARM_REG_R0, 0)
        ret(uc)
KU = 0xffff0000; mu.mem_map(KU, 0x1000); mu.mem_write(KU, b'\x1e\xff\x2f\xe1' * 0x400)  # bx lr
TLS = 0x5000000; mu.mem_map(TLS, 0x1000)
def kuser(uc, addr, size, ud):
    if addr == 0xffff0fc0:  # cmpxchg(oldval r0, newval r1, ptr r2) -> r0 = 0 on success
        o, n, p = uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1), uc.reg_read(UC_ARM_REG_R2)
        cur = int.from_bytes(uc.mem_read(p, 4), 'little')
        if cur == o: uc.mem_write(p, n.to_bytes(4, 'little')); uc.reg_write(UC_ARM_REG_R0, 0)
        else: uc.reg_write(UC_ARM_REG_R0, 1)
    elif addr == 0xffff0fe0: uc.reg_write(UC_ARM_REG_R0, TLS)
mu.hook_add(UC_HOOK_CODE, kuser, begin=KU, end=KU + 0x1000)
mu.hook_add(UC_HOOK_CODE, hook_code, begin=plt.virtual_address, end=0xc00000)
ia = lib.get_section('.init_array'); d = bytes(ia.content)
ok = bad = 0
for i in range(0, len(d), 4):
    f = int.from_bytes(d[i:i + 4], 'little')
    if not f or f == 0xffffffff: continue
    mu.reg_write(UC_ARM_REG_SP, STACK + SSZ - 0x1000)
    mu.reg_write(UC_ARM_REG_LR, RET | 1)
    try:
        mu.emu_start(f, RET, timeout=5_000_000, count=2_000_000); ok += 1
    except UcError as e:
        if bad < 5: print(hex(f), e, hex(mu.reg_read(UC_ARM_REG_PC)), file=sys.stderr)
        bad += 1
print(f'init funcs ok={ok} failed={bad} strings={len(found)}', file=sys.stderr)
json.dump({hex(k): v for k, v in found.items()}, open(sys.argv[2], 'w'), indent=0)
