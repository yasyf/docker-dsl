"""Console entry point: `docker-dsl <module.path> [--<key>=<value> ...] [--out PATH]`."""

from __future__ import annotations

from docker_dsl.__main__ import Main


def main() -> None:
    Main.run()
