// Decompiles every function whose demangled name matches the regex in args[0]
// and writes one .c file per function into args[1].
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import java.io.*;
import java.util.regex.*;

public class DumpDecomp extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] a = getScriptArgs();
        Pattern p = Pattern.compile(a[0]);
        File out = new File(a[1]);
        out.mkdirs();
        // Ghidra mis-detects many sdr:: helpers (e.g. String::assign) as noreturn; keep only real ones.
        java.util.Set<String> real = new java.util.HashSet<>(java.util.Arrays.asList(
            "abort", "exit", "_exit", "__cxa_throw", "__cxa_rethrow", "__cxa_end_cleanup", "__stack_chk_fail",
            "_Unwind_Resume", "___Unwind_Resume", "__assert2", "__cxa_bad_cast", "__cxa_bad_typeid",
            "__cxa_pure_virtual", "longjmp", "siglongjmp"));
        int cleared = 0;
        for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
            if (f.hasNoReturn() && !real.contains(f.getName()) && !f.getName().startsWith("__throw")
                    && !f.getName(true).startsWith("std::__throw")) { f.setNoReturn(false); cleared++; }
        }
        println("cleared noreturn on " + cleared);
        // ARM veneers: ldr ip,[pc,#d] ; add pc,pc,ip  |  ldr ip,[pc,#d] ; add ip,pc,ip ; bx ip
        int thunks = 0;
        ghidra.program.model.mem.Memory mem = currentProgram.getMemory();
        for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
            ghidra.program.model.address.Address ep = f.getEntryPoint();
            try {
                int i0 = mem.getInt(ep), i1 = mem.getInt(ep.add(4));
                ghidra.program.model.address.Address tgt = null;
                if ((i0 & 0xfffff000) == 0xe59fc000 && i1 == 0xe08ff00c) {        // ldr ip,[pc,#d]; add pc,pc,ip
                    int d = i0 & 0xfff; int v = mem.getInt(ep.add(8 + d)); tgt = ep.add(12 + v);
                } else if ((i0 & 0xfffff000) == 0xe59fc000 && i1 == 0xe08fc00c) { // ldr ip,[pc,#d]; add ip,pc,ip; bx ip
                    int d = i0 & 0xfff; int v = mem.getInt(ep.add(8 + d)); tgt = ep.add(12 + v);
                }
                if (tgt == null) continue;
                long off = tgt.getOffset() & ~1L;
                Function t = getFunctionAt(tgt.getNewAddress(off));
                if (t == null) t = createFunction(tgt.getNewAddress(off), null);
                if (t != null && t != f) { f.setThunkedFunction(t); thunks++; }
            } catch (Exception e) { }
        }
        println("marked thunks " + thunks);
        DecompInterface d = new DecompInterface();
        d.openProgram(currentProgram);
        int n = 0;
        for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
            String name = f.getName(true);
            if (!p.matcher(name).find()) continue;
            DecompileResults r = d.decompileFunction(f, 120, monitor);
            if (!r.decompileCompleted()) continue;
            String fn = name.replaceAll("[^A-Za-z0-9_.:-]", "_").replace("::", ".");
            if (fn.length() > 180) fn = fn.substring(0, 180);
            try (PrintWriter w = new PrintWriter(new File(out, fn + "@" + f.getEntryPoint() + ".c"))) {
                w.println("// " + name + " @ " + f.getEntryPoint());
                w.println(r.getDecompiledFunction().getC());
            }
            n++;
        }
        println("decompiled " + n + " functions");
    }
}
