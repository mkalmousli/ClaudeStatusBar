"""A cross-platform exclusive file lock.

Several Claude sessions render their statusline at the same moment, so the
read/merge/write of the state file has to be serialised.  POSIX has flock,
Windows has msvcrt.locking, and neither exists on the other.
"""

import contextlib
import os
import sys

if sys.platform == "win32":
    import msvcrt

    def _lock(handle):
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)

    def _unlock(handle):
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _lock(handle):
        fcntl.flock(handle, fcntl.LOCK_EX)

    def _unlock(handle):
        fcntl.flock(handle, fcntl.LOCK_UN)


@contextlib.contextmanager
def exclusive(path):
    """Hold an exclusive lock on `path` for the duration of the block."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a+b")
    try:
        handle.seek(0)
        try:
            _lock(handle)
        except OSError:
            pass          # an unlockable filesystem is better than a crash
        yield
    finally:
        with contextlib.suppress(OSError):
            _unlock(handle)
        handle.close()


def replace_atomic(tmp, target):
    """os.replace is atomic on POSIX and on Windows for same-volume moves."""
    os.replace(tmp, target)
