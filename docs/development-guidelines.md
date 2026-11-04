# Python development guidelines

These standards apply to **new or materially changed code**. Existing code is legacy until separately refactored; do not expand the scope of a feature PR just to enforce standards everywhere.

## Design and maintainability
- Prefer Python idioms and simple, readable modules over Java-style framework scaffolding. Apply KISS, YAGNI, DRY, separation of concerns, and SOLID where they solve a real problem. Avoid speculative abstractions.
- Separate domain decisions (candidate selection, trims, approvals, metadata rules) from IO (FFmpeg, ExifTool, Ollama, Nominatim, filesystem) and from Streamlit presentation. Keep business logic independently testable.
- Use small functions with explicit inputs and outputs; use type hints on public boundaries and nontrivial functions. Prefer `dataclass` for simple structured values and `Protocol` for interchangeable dependencies when useful. Do not introduce classes solely for style.
- Introduce a dedicated adapter per stock platform, with a consistent contract for platform-specific field mapping, validation and export. Keep platform-specific conditionals out of generic orchestration where practical. Preserve backward compatibility of existing outputs.
- Prefer composition and explicit dependency passing to global state, singleton services or DI frameworks.
- Follow PEP 8 and conventional Python naming. Use `pathlib`, context managers, clear exceptions, and structured logging instead of silent failures or print-based error handling in reusable components.

## Configuration and reproducibility
- Centralize configurable paths, service endpoints, model identifiers, timeouts, clip limits and thresholds; never scatter unexplained magic numbers. Preserve existing defaults until an approved migration.
- Use environment variables for deployment-specific settings and secrets, validated at startup or at the relevant boundary. Never commit credentials. Not every domain constant needs an environment variable: use named constants for invariant business rules.
- Make macOS ARM64 and Ubuntu x86_64 differences explicit and isolated. Declare dependencies in `pyproject.toml` and evaluate pinning/locking for reproducible environments.
- Add Ruff formatting/linting and a pragmatic type checker (for example Pyright) incrementally in a separate approved change; do not claim these checks are enforced before CI actually runs them.

## Testing before refactoring
- **Characterize behavior first.** Before substantial refactoring, document actual end-user journeys, observable outputs, edge cases, persistence/restart behavior, and failure recovery; add tests that detect regressions. Preserve behavior unless a change is explicitly approved.
- Prefer meaningful behavior coverage over an arbitrary 100% line-coverage target. Include analysis from real video, metadata extraction, candidate generation, review/edit/undo, stock-platform export, repeat runs and protection of originals.
- Use a layered suite: fast unit/component tests; real-tool integration tests using representative, licensed MP4 samples and temporary isolated directories; opt-in full E2E using actual Ollama models and representative video. Synthetic fixtures and mocks are valid for unit tests but **not evidence of real E2E behavior**.
- Default GitHub-hosted PR CI should run fast, deterministic checks without downloading multi-GB models. Evaluate the feasibility of hosted real-tool video integration in CI; run full AI E2E on an isolated, explicitly triggered runner with preinstalled models or a controlled download/cache strategy. A self-hosted Mac runner must never execute untrusted PR code or access the personal footage library.
- Verify real outputs: playable video, durations/codecs, metadata schemas, platform mappings, and no modification of originals. For nondeterministic AI outputs, validate stable contracts and quality constraints rather than exact prose.
- Never weaken tests to achieve green CI. Investigate failures and agree whether production behavior, the specification/test, or environment needs fixing; see `AGENTS.md` for mandatory failure triage.

## Change discipline
- Discuss architectural trade-offs and agree on an implementation plan for complex changes before coding.
- Keep feature work and broad refactoring in separate PRs when possible. Refactor incrementally behind characterization tests; review diffs for data safety and backward compatibility.
- Record substantial design decisions in `docs/design/` and keep `docs/architecture.md` aligned with verified implementation.
