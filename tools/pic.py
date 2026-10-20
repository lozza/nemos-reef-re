# Linear Thumb/ARM pass over libsdr.so that tracks PIC constants per register and records,
# for every BL, the known values of r0-r3. Output: calls.json (list of [site, target, regs]).
import sys, json, lief, capstone
from capstone import arm_const as A
lib = lief.parse(sys.argv[1])
text = lib.get_section('.text')
base, data = text.virtual_address, bytes(text.content)
def rd(a, n):
    try: return bytes(lib.get_content_from_virtual_address(a, n))
    except Exception: return b''
funcs = {}
for s in list(lib.symtab_symbols) + list(lib.dynamic_symbols):
    if s.value and s.name and s.type == lief.ELF.Symbol.TYPE.FUNC: funcs[s.value & ~1] = (s.name, s.value & 1, s.size)
plt = lib.get_section('.plt')
slots = {r.address: r.symbol.name for r in lib.pltgot_relocations if r.has_symbol}
_arm = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
_pd = bytes(plt.content)
for i in range(20, len(_pd), 12):  # ARM PLT entry: add ip,pc,#a ; add ip,ip,#b ; ldr pc,[ip,#c]!
    ins = list(_arm.disasm(_pd[i:i + 12], plt.virtual_address + i))
    if len(ins) != 3: continue
    try:
        imms = [int(x.op_str.split('#')[-1].rstrip(']!'), 16) for x in ins]
        got = plt.virtual_address + i + 8 + imms[0] + imms[1] + imms[2]
        if got in slots: funcs[plt.virtual_address + i] = (slots[got], 0, 0)
    except Exception: pass
ia = lib.get_section('.init_array'); _ia = bytes(ia.content)
_starts = sorted(funcs)
import bisect
for i in range(0, len(_ia), 4):
    v = int.from_bytes(_ia[i:i+4], 'little')
    if not v or (v & ~1) in funcs: continue
    j = bisect.bisect_right(_starts, v & ~1)
    end = _starts[j] if j < len(_starts) else (v & ~1) + 0x4000
    funcs[v & ~1] = (f'static_init_{v & ~1:x}', v & 1, min(end - (v & ~1), 0x10000))
# also give size-0 symbols a size up to the next symbol
_starts = sorted(funcs)
for k, a in enumerate(_starts):
    n, t, sz = funcs[a]
    if not sz and k + 1 < len(_starts) and a >= base: funcs[a] = (n, t, min(_starts[k + 1] - a, 0x10000))
md = {1: capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB), 0: capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)}
for m in md.values(): m.detail = True
REG = {A.ARM_REG_R0 + i: i for i in range(13)}
calls = []
for fa, (fname, thumb, size) in sorted(funcs.items()):
    if not size or size > 200000: continue
    off = fa - base
    if off < 0 or off + size > len(data): continue
    regs = {}
    for ins in md[thumb].disasm(data[off:off + size], fa):
        ops = ins.operands
        mn = ins.mnemonic
        pc = ins.address + (4 if thumb else 8)
        if mn in ('ldr', 'ldr.w') and len(ops) == 2 and ops[1].type == A.ARM_OP_MEM and ops[1].mem.base == A.ARM_REG_PC and ops[0].reg in REG:
            v = int.from_bytes(rd((pc & ~3) + ops[1].mem.disp, 4), 'little'); regs[REG[ops[0].reg]] = v
        elif mn in ('ldr', 'ldr.w') and len(ops) == 2 and ops[1].type == A.ARM_OP_MEM and ops[1].mem.base in REG and ops[1].mem.index == 0 and regs.get(REG[ops[1].mem.base]) is not None and ops[0].reg in REG:
            a = (regs[REG[ops[1].mem.base]] + ops[1].mem.disp) & 0xffffffff
            v = rd(a, 4); regs[REG[ops[0].reg]] = int.from_bytes(v, 'little') if len(v) == 4 else None
        elif mn == 'add' and len(ops) == 2 and ops[1].type == A.ARM_OP_REG and ops[1].reg == A.ARM_REG_PC and ops[0].reg in REG:
            r = REG[ops[0].reg]; regs[r] = (regs[r] + pc) & 0xffffffff if regs.get(r) is not None else None
        elif mn == 'add' and len(ops) == 3 and ops[2].type == A.ARM_OP_REG and ops[2].reg == A.ARM_REG_PC and ops[0].reg in REG and ops[1].reg in REG:
            r = REG[ops[1].reg]; regs[REG[ops[0].reg]] = (regs[r] + pc) & 0xffffffff if regs.get(r) is not None else None
        elif mn in ('mov', 'adds', 'movs') and len(ops) == 2 and ops[0].type == A.ARM_OP_REG and ops[0].reg in REG:
            if ops[1].type == A.ARM_OP_REG and ops[1].reg in REG: regs[REG[ops[0].reg]] = regs.get(REG[ops[1].reg])
            elif ops[1].type == A.ARM_OP_IMM and mn == 'adds':
                v = regs.get(REG[ops[0].reg]); regs[REG[ops[0].reg]] = None if v is None else (v + ops[1].imm) & 0xffffffff
            elif ops[1].type == A.ARM_OP_IMM: regs[REG[ops[0].reg]] = ops[1].imm
            else: regs[REG[ops[0].reg]] = None
        elif mn in ('adds', 'add', 'subs', 'sub') and len(ops) == 3 and ops[0].type == A.ARM_OP_REG and ops[0].reg in REG and ops[1].reg in REG and ops[2].type == A.ARM_OP_IMM:
            r = REG[ops[1].reg]; v = regs.get(r)
            regs[REG[ops[0].reg]] = None if v is None else (v + (ops[2].imm if mn.startswith('add') else -ops[2].imm)) & 0xffffffff
        elif mn == 'subs' and len(ops) == 2 and ops[0].reg in REG and ops[1].type == A.ARM_OP_IMM:
            v = regs.get(REG[ops[0].reg]); regs[REG[ops[0].reg]] = None if v is None else (v - ops[1].imm) & 0xffffffff
        elif mn in ('bl', 'blx') and ops and ops[0].type == A.ARM_OP_IMM:
            calls.append([ins.address, ops[0].imm, {i: regs.get(i) for i in range(4) if regs.get(i) is not None}, fa])
            for i in range(4): regs.pop(i, None)
            regs.pop(12, None)
        else:
            # anything writing a register invalidates it
            try:
                for r in ins.regs_access()[1]:
                    if r in REG: regs.pop(REG[r], None)
            except Exception: pass
json.dump({'calls': calls, 'funcs': {hex(k): v[0] for k, v in funcs.items()}}, open(sys.argv[2], 'w'))
print(len(calls), 'calls')
