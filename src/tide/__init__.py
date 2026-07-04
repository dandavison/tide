import sys

from .dispatcher import run


def main() -> None:
    run(sys.argv[1] if len(sys.argv) > 1 else "files")
