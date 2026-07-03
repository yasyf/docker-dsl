from __future__ import annotations

import argparse
import importlib
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from docker_dsl.context import Registry
from docker_dsl.core import Dockerfile


class Main:
    @classmethod
    def parse_bool(cls, value: str) -> bool:
        match value.lower():
            case "true" | "1" | "yes":
                return True
            case "false" | "0" | "no":
                return False
        raise argparse.ArgumentTypeError(f"expected true/false, got {value!r}")

    @classmethod
    def type_for(cls, type_: type) -> Callable[[str], Any]:
        return cls.parse_bool if type_ is bool else type_

    @classmethod
    def run(cls, argv: list[str] | None = None) -> None:
        args = sys.argv[1:] if argv is None else argv
        usage = "usage: docker-dsl <module.path> [--<key>=<value> ...] [--out PATH]"
        if args and args[0] in ("-h", "--help"):
            print(usage)
            return
        if not args:
            raise SystemExit(usage)
        module_path, *rest = args
        # The console script does not put the working directory on sys.path
        # (unlike `python -m`), so add it: recipes live in the caller's cwd.
        if (cwd := str(Path.cwd())) not in sys.path:
            sys.path.insert(0, cwd)
        module = importlib.import_module(module_path)
        schema = Registry.get(module)

        parser = argparse.ArgumentParser(prog=f"python -m docker_dsl {module_path}")
        parser.add_argument("--out", type=Path, default=None)
        for name, type_ in schema.items():
            parser.add_argument(f"--{name}", type=cls.type_for(type_), required=True)

        namespace = parser.parse_args(rest)
        out: Path | None = namespace.out
        config_values = {name: getattr(namespace, name) for name in schema}

        text = Dockerfile(module).render(path=out, **config_values)
        if out is None:
            sys.stdout.write(text)


if __name__ == "__main__":
    Main.run()
