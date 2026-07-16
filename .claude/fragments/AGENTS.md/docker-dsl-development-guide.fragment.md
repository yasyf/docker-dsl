# docker-dsl Development Guide

Imperative context-manager DSL for authoring multi-stage Dockerfiles. Published to PyPI as `docker-dsl`; the CLI is `docker-dsl`, run as `uvx docker-dsl`.

## Repository Structure

```
docker-dsl/
├── docker_dsl/      # The package — stages, run builder, mounts, smart apt, config context, render core, stub generator
├── examples/         # Self-contained recipe modules, rendered by the snapshot tests
├── tests/            # Pytest suite
├── .github/          # GitHub Actions workflows
├── AGENTS.md         # This file — shared conventions
└── README.md         # Project overview
```
