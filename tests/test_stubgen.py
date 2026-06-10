from __future__ import annotations

import ast
from pathlib import Path

import pytest

from docker_dsl.stubgen import CommandInfo, StubGen


class TestFilterNames:
    @pytest.fixture
    def reserved(self) -> frozenset[str]:
        _, names = StubGen.extract_real_methods()
        return names

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("git", True),
            ("apt-get", False),
            ("7z", False),
            ("class", False),
            ("_private", False),
            ("make", True),
            ("cmake", True),
            ("True", False),
            ("match", False),
        ],
        ids=["valid", "dash", "digit-start", "keyword", "underscore",
             "valid-make", "valid-cmake", "builtin-const", "soft-keyword"],
    )
    def test_is_valid_name(self, name: str, expected: bool) -> None:
        assert StubGen.is_valid_name(name) == expected

    def test_reserved_names_rejected(self, reserved: frozenset[str]) -> None:
        for name in ("stage", "echo", "cd", "install", "curl_bash", "apt_install"):
            assert not StubGen.is_valid_name(name, reserved=reserved)

    def test_filter_returns_sorted(self) -> None:
        assert StubGen.filter_names({"zebra", "alpha", "beta"}) == ["alpha", "beta", "zebra"]

    def test_filter_excludes_reserved(self, reserved: frozenset[str]) -> None:
        assert StubGen.filter_names({"git", "echo", "stage"}, reserved=reserved) == ["git"]


class TestRenderMethod:
    def test_plain_command_is_valid_syntax(self) -> None:
        rendered = StubGen.render_method("mkdir", CommandInfo())
        ast.parse(f"class R:\n{rendered}")
        tree = ast.parse(f"class R:\n{rendered}")
        methods = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        assert methods == ["mkdir"]

    def test_overloaded_command_is_valid_syntax(self) -> None:
        info = CommandInfo(subcommands=("clone", "push"), flags=("--help", "--depth"))
        rendered = StubGen.render_method("git", info)
        tree = ast.parse(f"from typing import Literal, overload\nclass R:\n{rendered}")
        methods = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        assert methods.count("git") == 3

    def test_overloaded_first_arg_has_literal(self) -> None:
        info = CommandInfo(subcommands=("clone", "push"))
        rendered = StubGen.render_method("git", info)
        assert 'Literal["clone", "push"]' in rendered

    def test_flags_become_kwargs(self) -> None:
        info = CommandInfo(flags=("--verbose", "--no-pager"))
        rendered = StubGen.render_method("curl", info)
        ast.parse(f"class R:\n{rendered}")
        assert "verbose" not in rendered

    def test_flags_with_subcommands_become_kwargs(self) -> None:
        info = CommandInfo(subcommands=("sub",), flags=("--verbose",))
        rendered = StubGen.render_method("tool", info)
        tree = ast.parse(f"from typing import Literal, overload\nclass R:\n{rendered}")
        funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "tool"]
        kwonly_sets = [{a.arg for a in f.args.kwonlyargs} for f in funcs]
        assert any("verbose" in s for s in kwonly_sets)


class TestFlagsToKwargs:
    def test_converts_dashes_to_underscores(self) -> None:
        result = StubGen.flags_to_kwargs(("--no-pager", "--depth"))
        assert ("no_pager", "str | bool") in result
        assert ("depth", "str | bool") in result

    def test_filters_keywords(self) -> None:
        result = StubGen.flags_to_kwargs(("--class", "--for", "--ok"))
        names = {n for n, _ in result}
        assert "ok" in names
        assert names.isdisjoint({"class", "for"})


class TestExtractRealMethods:
    def test_extracts_known_methods(self) -> None:
        real, reserved = StubGen.extract_real_methods()
        tree = ast.parse(f"class R:\n{real}")
        methods = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        assert {"__enter__", "__exit__", "__call__", "echo", "cd", "curl_bash", "install"}.issubset(methods)
        assert {"apt_install", "add_apt_ppa", "add_apt_repo"}.issubset(methods)
        assert "__getattr__" not in methods

    def test_reserved_includes_methods_and_fields(self) -> None:
        _, reserved = StubGen.extract_real_methods()
        assert {"echo", "cd", "install", "curl_bash", "apt_install", "add_apt_ppa"}.issubset(reserved)
        assert {"stage", "commands"}.issubset(reserved)


class TestParseManPage:
    @pytest.mark.skipif(not Path("/usr/share/man").exists(), reason="no man pages")
    def test_known_command_has_flags(self) -> None:
        info = StubGen.parse_man_page("ls")
        assert info.has_completions
        assert any(f.startswith("-") for f in info.flags)

    def test_nonexistent_command_empty(self) -> None:
        assert not StubGen.parse_man_page("zzz_nonexistent_cmd_1234").has_completions


class TestEndToEnd:
    def test_run_produces_parseable_stub(self, tmp_path: Path) -> None:
        out = tmp_path / "builder.pyi"
        StubGen.run(output=out)
        tree = ast.parse(out.read_text())
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        assert len(classes) == 1
        assert classes[0].name == "RunBuilder"
        methods = {n.name for n in ast.walk(classes[0]) if isinstance(n, ast.FunctionDef)}
        assert {"__enter__", "__exit__", "echo", "cd", "apt_install", "add_apt_ppa"}.issubset(methods)
        assert len(methods) > 100


class TestShippedStub:
    @pytest.fixture
    def stub_methods(self) -> set[str]:
        stub_path = Path(__file__).parent.parent / "docker_dsl" / "builder.pyi"
        tree = ast.parse(stub_path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "RunBuilder":
                return {item.name for item in node.body if isinstance(item, ast.FunctionDef)}
        raise AssertionError("RunBuilder not found in stub")

    def test_has_common_commands(self, stub_methods: set[str]) -> None:
        assert {"git", "make", "python", "mkdir", "ln"}.issubset(stub_methods)

    def test_excludes_field_names_as_methods(self, stub_methods: set[str]) -> None:
        assert {"stage", "commands"}.isdisjoint(stub_methods)

    def test_preserves_real_methods(self, stub_methods: set[str]) -> None:
        assert {"__enter__", "__exit__", "__call__", "echo", "cd", "curl_bash", "install"}.issubset(stub_methods)

    def test_preserves_apt_methods(self, stub_methods: set[str]) -> None:
        assert {"apt_install", "add_apt_ppa", "add_apt_repo"}.issubset(stub_methods)
