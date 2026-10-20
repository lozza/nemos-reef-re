# usage: jsontypes.py <file-addr hex> <len hex>
# Heuristic: for each key the function reads, report how the fetched JSON value is used next:
# a vtable accessor (asInt/asLong/asBool/asString/size/get...) or a call to another loader.
import sys, subprocess, re
ACC = {0x8: 'type()', 0xc: 'asInt', 0x10: 'asLong', 0x14: 'asFloat?', 0x18: 'asBool?', 0x1c: 'asString',
       0x20: 'at(i)->ARRAY', 0x24: 'size()->ARRAY', 0x28: 'get(key)->OBJECT', 0x2c: 'has(key)->OBJECT', 0x30: 'keyAt->OBJECT'}
out = subprocess.run(['python3', '-I', __import__('os').path.join(__import__('os').path.dirname(__file__), 'disx.py'), sys.argv[1], sys.argv[2]], capture_output=True, text=True).stdout.splitlines()
key, state, last_off = None, None, None
res = []
for line in out:
    m = re.search(r';\s*\[([A-Za-z_]+)\]', line)
    if m and ('add' in line or 'adds' in line):
        key, state = m.group(1), 'key'
        continue
    m = re.search(r'ldr\s+r3, \[r3, #(0x[0-9a-f]+)\]', line)
    if m: last_off = int(m.group(1), 16); continue
    if re.search(r'blx\s+r3', line) and last_off is not None:
        if state == 'key' and last_off in (0x28, 0x2c):
            state = 'got' if last_off == 0x28 else 'has'
        elif state == 'got':
            res.append((key, ACC.get(last_off, hex(last_off)))); state = None
        last_off = None; continue
    if 'JSONObject::safeGet' in line and state == 'key':
        state = 'got'; continue
    m = re.search(r'bl\s+#\S+\s+;\s+(.*)', line)
    if m and state == 'got' and 'safeGet' not in line and 'String' not in m.group(1):
        res.append((key, 'passed to ' + m.group(1)[:60])); state = None
seen = []
for k, t in res:
    if (k, t) not in seen: seen.append((k, t)); print('  %-32s %s' % (k, t))
