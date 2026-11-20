import os
import sys

INTERP = os.path.join(os.path.expanduser("~"), "virtualenv", "alkitab-api", "3.11", "bin", "python3")
if sys.executable != INTERP and os.path.exists(INTERP):
    os.execl(INTERP, INTERP, *sys.argv)

from app import app as application  # noqa: E402
