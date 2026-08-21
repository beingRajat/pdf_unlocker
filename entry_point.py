"""PyInstaller entry script.

PyInstaller needs a file to point at and cannot take `-m pdf_unlocker`, so this
shim exists purely for the frozen build. To run from source, prefer:

    python -m pdf_unlocker
"""

import sys

from pdf_unlocker.app import main

if __name__ == "__main__":
    sys.exit(main())
