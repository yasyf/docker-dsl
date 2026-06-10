from __future__ import annotations

import importlib

from docker_dsl import Dockerfile


class Demo:
    RECIPES: tuple[tuple[str, dict[str, object]], ...] = (
        ("examples.minimal", {"tag": "v1.0.0"}),
        ("examples.multi_stage", {"release": True}),
        ("examples.multi_stage", {"release": False}),
        ("examples.apt_smart", {"with_intel": True}),
        ("examples.apt_smart", {"with_intel": False}),
    )

    @classmethod
    def run(cls) -> None:
        for module_path, config in cls.RECIPES:
            module = importlib.import_module(module_path)
            text = Dockerfile(module).render(**config)
            header = f"# --- {module_path} {config} ---"
            print(header)
            print(text)
            print()


if __name__ == "__main__":
    Demo.run()
