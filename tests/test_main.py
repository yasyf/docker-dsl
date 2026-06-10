from __future__ import annotations

import subprocess
import sys
from pathlib import Path


class TestCLI:
    @staticmethod
    def write_recipe(tmp_path: Path, name: str, source: str) -> tuple[Path, str]:
        file = tmp_path / f"{name}.py"
        file.write_text(source)
        return file, name

    @staticmethod
    def run_cli(tmp_path: Path, module_name: str, *args: str) -> subprocess.CompletedProcess[str]:
        env = {"PYTHONPATH": str(tmp_path)}
        return subprocess.run(
            [sys.executable, "-m", "docker_dsl", module_name, *args],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

    def test_renders_to_stdout(self, tmp_path: Path) -> None:
        source = (
            "from docker_dsl import Stage, context as ctx\n"
            "ctx.register('gpu', bool)\n"
            "with Stage('ubuntu:24.04' if not ctx.gpu else 'nvidia:latest') as s:\n"
            "    s.workdir('/root')\n"
        )
        self.write_recipe(tmp_path, "recipe_cli_stdout", source)
        result = self.run_cli(tmp_path, "recipe_cli_stdout", "--gpu=false")
        assert result.returncode == 0, result.stderr
        assert "FROM ubuntu:24.04 AS base" in result.stdout
        assert "WORKDIR /root" in result.stdout

    def test_renders_to_file(self, tmp_path: Path) -> None:
        source = (
            "from docker_dsl import Stage, context as ctx\n"
            "ctx.register('gpu', bool)\n"
            "with Stage('ubuntu:24.04') as s:\n"
            "    s.workdir('/root')\n"
        )
        self.write_recipe(tmp_path, "recipe_cli_file", source)
        out = tmp_path / "Dockerfile.out"
        result = self.run_cli(tmp_path, "recipe_cli_file", "--gpu=false", "--out", str(out))
        assert result.returncode == 0, result.stderr
        assert result.stdout == ""
        assert out.exists()
        assert "FROM ubuntu:24.04" in out.read_text()

    def test_bool_true_parsed(self, tmp_path: Path) -> None:
        source = (
            "from docker_dsl import Stage, context as ctx\n"
            "ctx.register('gpu', bool)\n"
            "with Stage('gpu-image' if ctx.gpu else 'cpu-image') as s:\n"
            "    s.workdir('/root')\n"
        )
        self.write_recipe(tmp_path, "recipe_cli_bool", source)
        result = self.run_cli(tmp_path, "recipe_cli_bool", "--gpu=true")
        assert result.returncode == 0, result.stderr
        assert "FROM gpu-image AS base" in result.stdout

    def test_missing_required_flag_errors(self, tmp_path: Path) -> None:
        source = (
            "from docker_dsl import Stage, context as ctx\n"
            "ctx.register('gpu', bool)\n"
            "with Stage('ubuntu:24.04') as s:\n"
            "    s.workdir('/root')\n"
        )
        self.write_recipe(tmp_path, "recipe_cli_missing", source)
        result = self.run_cli(tmp_path, "recipe_cli_missing")
        assert result.returncode != 0
        assert "gpu" in result.stderr
