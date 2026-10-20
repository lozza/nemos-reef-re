# Strips Ghidra noise from decompiled sdr code: inlined String destructors, vtable resets, empty ifs.
import sys, re
for path in sys.argv[1:]:
    t = open(path).read()
    t = re.sub(r'\n\s*if \(\w+ != \(void \*\)0x0\) \{\n\s*operator_delete__\(\w+\);\n\s*return(?: \w+)?;\n\s*\}', '', t)
    t = re.sub(r'\n\s*if \(\w+ != \(void \*\)0x0\) \{\n\s*operator_delete__\(\w+\);\n\s*\}', '', t)
    t = re.sub(r'\n\s*\w+ = (?:\*\(int \*\)\([^;]*\)|iVar\d+|uVar\d+) \+ 8;(?=\n)', '', t)
    t = re.sub(r'\n\s*(?:local|[ai]Stack|pv?Stack|iStack)_\w+ = \w+ \+ 8;', '', t)
    sys.stdout.write(f'//// {path}\n' + t)
