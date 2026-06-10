# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-06-10

### Added
- Initial release, extracted from the BioQA monorepo.
- `Stage` context manager with stage derivation, `COPY --from`, env scopes,
  and BuildKit cache/secret/bind mount scopes.
- `RunBuilder` with dynamic shell-command dispatch, `cd` scoping, and echo
  redirects.
- Smart apt helpers (`apt_install`, `add_apt_ppa`, `add_apt_repo`) with
  automatic `apt-get update` buffer flushing.
- Two-pass recipe execution: pydantic-validated config fields registered via
  `context.register`, rendered with `Dockerfile(module).render(**config)`.
- `docker-dsl` CLI (and `python -m docker_dsl`) with per-recipe dynamic
  arguments.
- Generated `builder.pyi` editor completions via `python -m docker_dsl.stubgen`.

[Unreleased]: https://github.com/yasyf/docker-dsl/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/yasyf/docker-dsl/releases/tag/v0.1.0
