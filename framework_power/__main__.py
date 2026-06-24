"""Enable `python -m framework_power ...`."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
