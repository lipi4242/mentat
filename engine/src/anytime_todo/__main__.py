"""`python3 -m anytime_todo …` = `python3 -m anytime_todo.cli …`.

Guarded: the engine's plugin loader imports every submodule of a pack, and an
import must never run the command line.
"""
from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
