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
