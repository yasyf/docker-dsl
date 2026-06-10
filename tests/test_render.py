from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from docker_dsl import Dockerfile


class TestRender:
    @staticmethod
    def make_recipe(tmp_path: Path, name: str, source: str) -> ModuleType:
        file = tmp_path / f"{name}.py"
        file.write_text(source)
        spec = importlib.util.spec_from_file_location(name, file)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod

    def test_minimal_single_stage(self, tmp_path: Path) -> None:
        source = (
            "from docker_dsl import Stage, context as ctx\n"
            "ctx.register('gpu', bool)\n"
            "with Stage('ubuntu:24.04' if not ctx.gpu else 'nvidia:latest') as s:\n"
            "    s.arg('PY', '3.13', env=True)\n"
            "    s.workdir('/root')\n"
        )
        mod = self.make_recipe(tmp_path, "recipe_minimal", source)
        with Dockerfile(mod) as d:
            text = d.render(gpu=False)
        assert text == (
            "# syntax=docker/dockerfile:1\nFROM ubuntu:24.04 AS base\nARG PY=3.13\nENV PY=${PY}\nWORKDIR /root\n"
        )

    def test_gpu_branch(self, tmp_path: Path) -> None:
        source = (
            "from docker_dsl import Stage, context as ctx\n"
            "ctx.register('gpu', bool)\n"
            "with Stage('nvcr.io/nvidia/pytorch:26.03-py3' if ctx.gpu else 'ubuntu:24.04') as s:\n"
            "    s.env({'CUDA_MODULE_LOADING': 'LAZY' if ctx.gpu else None, 'PATH_FLAG': 'set'})\n"
        )
        mod = self.make_recipe(tmp_path, "recipe_gpu", source)
        with Dockerfile(mod) as d:
            gpu_text = d.render(gpu=True)
            cpu_text = d.render(gpu=False)
        assert "FROM nvcr.io/nvidia/pytorch:26.03-py3 AS base" in gpu_text
        assert "ENV CUDA_MODULE_LOADING=LAZY" in gpu_text
        assert "CUDA_MODULE_LOADING" not in cpu_text
        assert "ENV PATH_FLAG=set" in cpu_text

    def test_multi_stage_with_copy(self, tmp_path: Path) -> None:
        source = (
            "from docker_dsl import Stage, context as ctx\n"
            "ctx.register('gpu', bool)\n"
            "with Stage('ubuntu:24.04') as base:\n"
            "    base.workdir('/root')\n"
            "with base.stage() as builder:\n"
            "    builder.run('echo', 'hello')\n"
            "with base.stage() as release:\n"
            "    release.copy('/out', stage=builder)\n"
        )
        mod = self.make_recipe(tmp_path, "recipe_multi", source)
        with Dockerfile(mod) as d:
            text = d.render(gpu=False)
        assert "FROM ubuntu:24.04 AS base" in text
        assert "FROM base AS builder" in text
        assert "FROM base AS release" in text
        assert "COPY --from=builder --link /out /out" in text
        assert "RUN echo hello" in text

    def test_render_writes_to_path(self, tmp_path: Path) -> None:
        source = (
            "from docker_dsl import Stage, context as ctx\n"
            "ctx.register('gpu', bool)\n"
            "with Stage('ubuntu:24.04') as s:\n"
            "    s.workdir('/root')\n"
        )
        mod = self.make_recipe(tmp_path, "recipe_path", source)
        out = tmp_path / "Dockerfile"
        with Dockerfile(mod) as d:
            text = d.render(path=out, gpu=False)
        assert out.read_text() == text
        assert "FROM ubuntu:24.04" in text

    def test_render_is_idempotent_across_calls(self, tmp_path: Path) -> None:
        source = (
            "from docker_dsl import Stage, context as ctx\n"
            "ctx.register('gpu', bool)\n"
            "with Stage('ubuntu:24.04') as s:\n"
            "    s.workdir('/root')\n"
        )
        mod = self.make_recipe(tmp_path, "recipe_idemp", source)
        with Dockerfile(mod) as d:
            first = d.render(gpu=False)
            second = d.render(gpu=False)
        assert first == second

    def test_register_is_caller_scoped(self, tmp_path: Path) -> None:
        from docker_dsl.context import Registry

        source_a = (
            "from docker_dsl import Stage, context as ctx\n"
            "ctx.register('gpu', bool)\n"
            "with Stage('a') as s:\n"
            "    s.workdir('/a')\n"
        )
        source_b = (
            "from docker_dsl import Stage, context as ctx\n"
            "ctx.register('mode', str)\n"
            "with Stage('b') as s:\n"
            "    s.workdir('/b')\n"
        )
        mod_a = self.make_recipe(tmp_path, "recipe_scope_a", source_a)
        mod_b = self.make_recipe(tmp_path, "recipe_scope_b", source_b)
        assert "gpu" in Registry.get(mod_a)
        assert "mode" in Registry.get(mod_b)
        assert "mode" not in Registry.get(mod_a)

    def test_missing_field_raises(self, tmp_path: Path) -> None:
        import pydantic

        source = (
            "from docker_dsl import Stage, context as ctx\n"
            "ctx.register('gpu', bool)\n"
            "with Stage('ubuntu:24.04') as s:\n"
            "    s.workdir('/root')\n"
        )
        mod = self.make_recipe(tmp_path, "recipe_missing", source)
        with Dockerfile(mod) as d:
            try:
                d.render()
            except pydantic.ValidationError:
                return
        raise AssertionError("expected ValidationError")
