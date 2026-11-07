"""SubScout: themed, journalistic data narratives (Read and Present modes)."""

__version__ = "0.2.0"


def metric(*args, **kwargs):
    """A number a story's prose may quote. See styleguide/story-format.md."""
    from .build import metric as _metric

    return _metric(*args, **kwargs)


def main() -> int:
    from .cli import main as _main

    return _main()
