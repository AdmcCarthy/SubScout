"""SubScout: themed, journalistic data narratives (Read and Present modes)."""

__version__ = "0.1.0"


def main() -> int:
    from .cli import main as _main

    return _main()
