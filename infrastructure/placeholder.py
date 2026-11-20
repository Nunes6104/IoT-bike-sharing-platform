"""Keep a deliberately unimplemented service boundary visible in Compose."""

import signal
import sys
import threading


stop = threading.Event()
for signum in (signal.SIGINT, signal.SIGTERM):
    signal.signal(signum, lambda _signum, _frame: stop.set())

print(f"{sys.argv[1]} is a placeholder; no application functionality is running.")
stop.wait()
