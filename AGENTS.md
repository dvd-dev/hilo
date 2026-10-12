# Coding Assistant Instructions: Hilo Home Assistant Custom Integration

This repository contains the Hilo custom component (`custom_components/hilo`) for Home Assistant, an integration connecting Hilo smart home energy devices and services.

## Git Commit Guidelines

- **First line**: Short, specific imperative sentence (e.g. "Add snapshot tests for switch platform"). No emojis in titles.
- **Commit description**: Focus on the **WHY** (problem, context, and architectural rationale). Do not merely recite the diff. Keep it concise, factual, and proportional.
- **Do NOT amend, squash, or rebase commits that have already been pushed to the PR branch after the PR is opened**: Reviewers need to follow the commit history and see what changed since their last review.

## Development Commands

- In the devcontainer, the sibling library `python-hilo` is mounted at `/workspaces/python-hilo`.
- Run `scripts/setup` to configure the environment and install dependencies. If a local `python-hilo` clone is present, it will be installed in editable development mode (`uv pip install -e /workspaces/python-hilo`).
- Use `scripts/develop` to launch a local Home Assistant test instance with `--skip-pip-packages python-hilo`.
- Run tests: `uv run pytest` or `uv run pytest tests/test_<platform>.py`.
- Update Syrupy snapshots: `uv run pytest tests/test_<platform>.py --snapshot-update`.
- Check linting and formatting: `uv run ruff check .` and `uv run ruff format --check .`.

## Python Syntax Notes

- Maintain compatibility with Home Assistant Core versions released up to 1 year back: **Python 3.13 is the minimum supported version** (CI tests both Python 3.13 and 3.14).
- Do not use Python 3.14-exclusive syntax (such as unparenthesized `except TypeA, TypeB:` or PEP 649 unquoted forward annotations without `from __future__ import annotations`) that would break on Python 3.13.
- When shims are required for backwards compatibility across Home Assistant versions, annotate them with:
  `# TODO: Remove once support for Home Assistant <YYYY.M is dropped`.

## Testing

Follow official Home Assistant testing guides:
- [Writing tests for integrations](https://developers.home-assistant.io/docs/development_testing/#writing-tests-for-integrations)
- [Snapshot testing](https://developers.home-assistant.io/docs/development_testing/#snapshot-testing)
- [Integration Quality Scale](https://developers.home-assistant.io/docs/integration_quality_scale_index/)

- Use `pytest-homeassistant-custom-component` and Syrupy snapshot testing (`snapshot_platform`).
- Use `.ambr` snapshots instead of repetitive, exhaustive manual assertions in Python code.
- Isolate target platforms using the test helper in `tests/__init__.py`:
  ```python
  await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SWITCH], mock_api)
  await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
  ```
- Test service actions (`SERVICE_TURN_ON`, `SERVICE_TURN_OFF`) through `await hass.services.async_call(DOMAIN, SERVICE, {...}, blocking=True)` and snapshot the resulting states.
- When writing tests or implementation code, ensure all parameters have precise type annotations (prefer concrete types like `HomeAssistant`, `MockConfigEntry`, `SnapshotAssertion`). **The use of `Any` is strictly forbidden in new code.**
- **Single purpose tests**: Each test function must verify only one specific behavior or outcome. Avoid testing multiple unrelated scenarios in a single test; split them into focused tests or use parametrization.
- Prefer `@pytest.mark.usefixtures` over unused test function arguments.
- Avoid branching (`if`/`else`) inside tests. Instead, split the test or use `@pytest.mark.parametrize` with `pytest.param(..., id="...")` to name cases clearly.
- Hardcoded `entity_id`s in tests are acceptable. If repeated across multiple tests, use a constant.
- Avoid "test theater": test real integration logic, not mock mechanics or Home Assistant Core internals.
- Prefer standard library `unittest.mock` (`AsyncMock`, `MagicMock`) over large bespoke stub classes. Never add hacky library imports (e.g. `pycares.Channel()`) to test files.
- Fixtures: Test fixtures (such as `tests/fixtures/all_devices.json`) must reflect real device schemas with sanitized identifiers (no personal tokens, MACs, or user IDs).

## Good practices

- Refer to Gold or Platinum integrations in Home Assistant Core ([`homeassistant/components`](https://github.com/home-assistant/core/tree/dev/homeassistant/components) and tests in [`tests/components`](https://github.com/home-assistant/core/tree/dev/tests/components)) as high-quality reference implementations.
- **Strict Version Pin Parity**: [`manifest.json`](custom_components/hilo/manifest.json) (`requirements`) and [`pyproject.toml`](pyproject.toml) (`[dependency-groups].test`) MUST always pin `python-hilo` to the exact same version (`python-hilo==YYYY.MM.MICRO`). Never bump one without the other.
- **State Machine Invariants**: Never invoke `hass.states.async_set()` directly on foreign entities, utility meters, or integration sensors. Never scan all entities via `hass.states.async_all()` during coordinator updates.
- **Non-Blocking I/O**: Never perform synchronous disk operations on the asyncio event loop. Always pass explicit paths via `hass.config.path(...)` and delegate blocking work to executor threads: `await hass.async_add_executor_job(...)`.
- **Validation & Schemas**: Do not add redundant defensive checks for inputs already validated by Home Assistant action/service schemas.
- When validation guarantees a dict key exists, prefer direct key access (`data["key"]`) instead of `.get("key")` so contract violations surface immediately.
- **Exception Handling**: Keep `try` clauses as small as possible. Avoid wrapping large blocks of code or catching exceptions from functions not expected to raise them.
- **Comments**: Keep comments concise. Explain non-obvious constraints (the WHY), never what the code does. Do not add section or divider comments (`# --- XYZ ---`).
- **Secrets**: Never log access tokens, refresh tokens, passwords, or raw JWT payloads in `DEBUG` or `INFO` logs.

## AI policy

Autonomous contributions are not accepted. Every change must be reviewed and understood by a human contributor before submission. Never open pull requests, create release tags, or post comments autonomously without explicit contributor instruction.
