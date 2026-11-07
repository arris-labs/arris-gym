# Last words on stderr, where a kernel abort writes its reason, then `abort`.
# The worker is PID 1 of its PID namespace, to which the kernel does not
# deliver the SIGABRT `abort` raises; glibc then executes its abort
# instruction, `hlt` on x86-64, which ends the process by SIGSEGV.
import os
import sys

sys.stderr.write("the last words\n")
sys.stderr.flush()
os.abort()
