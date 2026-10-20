# usage: disx.py <file-addr hex> <len hex>  - Thumb disassembly with PIC keys, strings and call names
import sys, json, lief, capstone, subprocess, bisect
from capstone import arm_const as A
lib = lief.parse(sys.argv[3] if len(sys.argv) > 3 else 'libsdr.so')
g = {int(k, 16): v for k, v in json.load(open('gstrings_emu.json')).items() if 0xc31000 <= int(k, 16) < 0xfd6000}
syms = [s for s in list(lib.symtab_symbols) + list(lib.dynamic_symbols) if s.value and s.type == lief.ELF.Symbol.TYPE.FUNC]
fs = {s.value & ~1: s.name for s in syms}
dm = lambda n: subprocess.run(['c++filt', n], capture_output=True, text=True).stdout.strip()
rd = lambda a, n: bytes(lib.get_content_from_virtual_address(a, n))
arm = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
def thunk(a):
    ins = list(arm.disasm(rd(a, 12), a))
    if len(ins) >= 2 and ins[0].mnemonic == 'ldr' and 'ip, [pc' in ins[0].op_str:
        d = int(ins[0].op_str.split('#')[1].rstrip(']'), 16) if '#' in ins[0].op_str else 0
        return (a + 12 + int.from_bytes(rd(a + 8 + d, 4), 'little')) & 0xffffffff
def name(t):
    n = fs.get(t & ~1) or fs.get((thunk(t & ~1) or 0) & ~1)
    return dm(n)[:90] if n else hex(t)
def cstr(a):
    try:
        b = rd(a, 80).split(b'\0')[0]
        return b.decode() if len(b) > 1 and all(32 <= c < 127 for c in b) else None
    except Exception: return None
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB); md.detail = True
start, ln = int(sys.argv[1], 16), int(sys.argv[2], 16)
regs = {}
for i in md.disasm(rd(start, ln), start):
    o = i.operands; x = ''; pc = i.address + 4
    if i.mnemonic == 'ldr' and len(o) == 2 and o[1].type == A.ARM_OP_MEM and o[1].mem.base == A.ARM_REG_PC:
        regs[o[0].reg] = int.from_bytes(rd((pc & ~3) + o[1].mem.disp, 4), 'little')
    elif i.mnemonic == 'add' and len(o) == 2 and o[1].type == A.ARM_OP_REG and o[1].reg == A.ARM_REG_PC and o[0].reg in regs:
        v = (regs[o[0].reg] + pc) & 0xffffffff; regs[o[0].reg] = v
        x = '  ; ' + (('[' + g[v] + ']') if v in g else (repr(cstr(v)) if cstr(v) else hex(v)))
    elif i.mnemonic in ('adds', 'add') and len(o) == 3 and o[2].type == A.ARM_OP_IMM and o[1].reg in regs:
        v = (regs[o[1].reg] + o[2].imm) & 0xffffffff; regs[o[0].reg] = v
        if v in g: x = '  ; [' + g[v] + ']'
    elif i.mnemonic in ('adds',) and len(o) == 2 and o[1].type == A.ARM_OP_IMM and o[0].reg in regs:
        v = (regs[o[0].reg] + o[1].imm) & 0xffffffff; regs[o[0].reg] = v
        if v in g: x = '  ; [' + g[v] + ']'
    if i.mnemonic in ('bl', 'blx') and i.op_str.startswith('#'):
        x = '  ; ' + name(int(i.op_str[1:], 16))
    print('%08x  %-7s %s%s' % (i.address, i.mnemonic, i.op_str, x))
