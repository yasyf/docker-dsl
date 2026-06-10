from __future__ import annotations

import ast
import json
import keyword
import os
import re
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent / "_completions.sh"
BUILDER_PATH = Path(__file__).parent / "builder.py"
APT_PATH = Path(__file__).parent / "apt.py"
DEFAULT_OUTPUT = Path(__file__).parent / "builder.pyi"
# These builtins complete live env-var names, which would embed the generating
# machine's environment — including secret names — into the shipped stub.
ENV_COMPLETING_BUILTINS = frozenset({"export", "declare"})


@dataclass(frozen=True)
class CommandInfo:
    subcommands: tuple[str, ...] = ()
    flags: tuple[str, ...] = ()

    @property
    def has_completions(self) -> bool:
        return bool(self.subcommands or self.flags)


class StubGen:
    @classmethod
    def discover_from_bash(cls) -> tuple[set[str], dict[str, CommandInfo]]:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp = f.name
        try:
            subprocess.run(
                ["bash", "-lic", f"source {SCRIPT_PATH} {tmp}"],
                capture_output=True,
                timeout=120,
            )
            data = json.loads(Path(tmp).read_text())
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            return set(), {}
        finally:
            Path(tmp).unlink(missing_ok=True)
        commands = set(data.get("commands", []))
        completions = {
            cmd: CommandInfo(
                subcommands=tuple(sorted(info["subcommands"])),
                flags=tuple(sorted(info["flags"])),
            )
            for cmd, info in data.get("completions", {}).items()
            if cmd not in ENV_COMPLETING_BUILTINS
        }
        return commands, completions

    @classmethod
    def parse_man_page(cls, cmd: str) -> CommandInfo:
        try:
            result = subprocess.run(
                ["man", cmd],
                capture_output=True,
                timeout=5,
                env={"PATH": os.environ.get("PATH", ""), "MANPAGER": "cat", "COLUMNS": "200"},
            )
            text = subprocess.run(
                ["col", "-b"],
                input=result.stdout,
                capture_output=True,
                timeout=5,
            ).stdout.decode("utf-8", errors="replace")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return CommandInfo()

        short_flags = set(re.findall(r"^\s+-([A-Za-z])\b", text, re.MULTILINE))
        long_flags = set(re.findall(r"^\s+(--[\w][\w-]*)", text, re.MULTILINE))
        flags = tuple(sorted({f"-{f}" for f in short_flags} | long_flags))
        return CommandInfo(flags=flags) if flags else CommandInfo()

    @classmethod
    def discover_from_man(
        cls, commands: set[str], already_have: dict[str, CommandInfo], *, reserved: frozenset[str] = frozenset()
    ) -> dict[str, CommandInfo]:
        need_man = [cmd for cmd in cls.filter_names(commands, reserved=reserved) if cmd not in already_have]
        with ProcessPoolExecutor(max_workers=os.cpu_count() or 4) as pool:
            results = pool.map(cls.parse_man_page, need_man, chunksize=50)
        return {cmd: info for cmd, info in zip(need_man, results, strict=True) if info.has_completions}

    @classmethod
    def is_valid_name(cls, name: str, *, reserved: frozenset[str] = frozenset()) -> bool:
        return (
            name.isidentifier()
            and not keyword.iskeyword(name)
            and not keyword.issoftkeyword(name)
            and not name.startswith("_")
            and name not in reserved
        )

    @classmethod
    def filter_names(
        cls, names: set[str] | dict[str, CommandInfo], *, reserved: frozenset[str] = frozenset()
    ) -> list[str]:
        raw = names if isinstance(names, set) else set(names.keys())
        return sorted(name for name in raw if cls.is_valid_name(name, reserved=reserved))

    @classmethod
    def extract_real_methods(cls) -> tuple[str, frozenset[str]]:
        names: set[str] = set()
        lines: list[str] = []

        for path, class_name in [(BUILDER_PATH, "RunBuilder"), (APT_PATH, "AptMixin")]:
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef) or node.name != class_name:
                    continue
                for item in node.body:
                    match item:
                        case ast.FunctionDef(name=name) if name != "__getattr__":
                            names.add(name)
                            lines.append(cls.format_method_stub(item))
                        case ast.AnnAssign(target=ast.Name(id=field_name)):
                            names.add(field_name)
                            lines.append(f"    {ast.unparse(item)}")

        return "\n".join(lines), frozenset(names)

    @classmethod
    def format_method_stub(cls, func: ast.FunctionDef) -> str:
        sig = ast.unparse(func.args) if func.args.args else ""
        returns = ast.unparse(func.returns) if func.returns else "None"
        decorators = "".join(f"    @{ast.unparse(d)}\n" for d in func.decorator_list)
        return f"{decorators}    def {func.name}({sig}) -> {returns}: ..."

    @classmethod
    def render_method(cls, name: str, info: CommandInfo) -> str:
        if not info.has_completions:
            return (
                f"    def {name}(self, *args: str, env: dict[str, str] | None = None, **kwargs: str | bool)"
                " -> None: ..."
            )

        lines: list[str] = []
        flag_kwargs = cls.flags_to_kwargs(info.flags)

        if info.subcommands:
            literal = ", ".join(f'"{s}"' for s in info.subcommands)
            lines.append("    @overload")
            params = ["self", f"subcmd: Literal[{literal}]", "/", "*args: str"]
            params.append("env: dict[str, str] | None = None")
            params.extend(f"{k}: {t} = ..." for k, t in flag_kwargs)
            lines.append(f"    def {name}({', '.join(params)}) -> None: ...")

        lines.append("    @overload")
        lines.append(
            f"    def {name}(self, *args: str, env: dict[str, str] | None = None, **kwargs: str | bool) -> None: ..."
        )
        lines.append(
            f"    def {name}(self, *args: str, env: dict[str, str] | None = None, **kwargs: str | bool) -> None: ..."
        )
        return "\n".join(lines)

    @classmethod
    def flags_to_kwargs(cls, flags: tuple[str, ...]) -> list[tuple[str, str]]:
        result: list[tuple[str, str]] = []
        for flag in flags:
            name = flag.lstrip("-").replace("-", "_")
            if not name.isidentifier() or keyword.iskeyword(name) or name in {"self", "args", "env", "kwargs"}:
                continue
            result.append((name, "str | bool"))
        return result

    @classmethod
    def render_stub(cls, commands: dict[str, CommandInfo], real_methods: str) -> str:
        lines = [
            "# @generated by python -m docker_dsl.stubgen — do not edit",
            "from __future__ import annotations",
            "",
            "from dataclasses import dataclass, field",
            "from types import TracebackType",
            "from typing import Literal, Self, overload",
            "",
            "from docker_dsl.run import CdScope, RedirectableCmd, ShellCommand",
            "from docker_dsl.stage import Stage",
            "",
            "",
            "@dataclass",
            "class RunBuilder:",
            real_methods,
        ]
        for name in sorted(commands.keys()):
            lines.append(cls.render_method(name, commands[name]))
        lines.append("")
        return "\n".join(lines)

    @classmethod
    def run(cls, output: Path | None = None) -> None:
        real_methods, reserved = cls.extract_real_methods()

        all_commands, bash_completions = cls.discover_from_bash()
        man_completions = cls.discover_from_man(all_commands, bash_completions, reserved=reserved)

        merged: dict[str, CommandInfo] = {}
        for name in cls.filter_names(all_commands, reserved=reserved):
            merged[name] = bash_completions.get(name, man_completions.get(name, CommandInfo()))

        text = cls.render_stub(merged, real_methods)
        target = output or DEFAULT_OUTPUT
        target.write_text(text)
        rich_count = sum(1 for v in merged.values() if v.has_completions)
        print(f"wrote {len(merged)} commands ({rich_count} with completions) to {target}")


if __name__ == "__main__":
    StubGen.run()
