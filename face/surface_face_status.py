# Tells the surface-kit shell extension how a face check is going, for the unlock
# animation: scan, match, fail or hide in /run/surface-kit-face/state. Howdy runs
# this as root during login. Only the picture depends on it, so nothing here may
# ever get in the way of the check itself.
import atexit
import os
import time

STATE_DIR = "/run/surface-kit-face"
STATE = os.path.join(STATE_DIR, "state")

# compare.py's exit codes: no match in time, too dark
FAILED = (11, 13)


def _write(state):
	try:
		os.makedirs(STATE_DIR, mode=0o755, exist_ok=True)
		tmp = f"{STATE}.{os.getpid()}"
		with open(tmp, "w") as f:
			f.write(f"{state} {time.time():.3f}\n")
		os.chmod(tmp, 0o644)
		os.replace(tmp, STATE)
	except OSError:
		pass


def scanning():
	_write("scan")
	# however the check ends, the picture mustn't stay up
	atexit.register(_write, "hide")


def finished(code):
	atexit.unregister(_write)
	_write("match" if code == 0 else "fail" if code in FAILED else "hide")
