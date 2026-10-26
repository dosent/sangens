# Sangens HA Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Default recommendation: inline execution in the current session; no delegation unless selected by the user.

**Goal:** One shared Sangens connection and a mobile-friendly sauna card for W12G / Sangens 6–9, with verified telemetry and explicit control.

**Architecture:** An asynchronous HTTP client feeds one HA coordinator per account. Config entries store server credentials once; entities expose state and commands through HA. A local custom card uses those entities and an optional locally hosted smoke video; no cloud credentials reach the frontend.

**Tech Stack:** Python, aiohttp supplied by HA, config flows, DataUpdateCoordinator, JavaScript custom element, pytest and Node test runner. Target installed HA 2026.10.4; establish a supported minimum version from the APIs actually used rather than retaining the untested README badge.

**Spec:** `docs/superpowers/specs/2026-10-27-sangens-ha-design.md`

## Global Constraints

- Domain and directory: `sangens`. Existing user files are preserved; work on `codex/sangens-ha-control`.
- One server-side setup for all HA users; no account token in browser requests, card config, logs or diagnostics.
- Initial poll interval: 30 seconds; serialize access and back off on errors/rate limits.
- Exact power payload values from the app: `ON` and `off`; no toggle, startup command, queued command or automatic command retry.
- User-binding ID and microchip ID are separate; serial number and PIN are not cloud credentials.
- Block temperature/mode changes while off until their non-starting semantics are verified.
- No real heating tests during implementation; live testing starts with read-only telemetry.
- Preserve standard controls as fallback. Original APK media remain outside the public repository.
- Commit independently verified milestones; push the feature branch, never force-push or merge without a request.

## Review Focus

- Account with multiple stoves: commands must target the selected microchip, not the binding ID or first returned device.
- Unknown/missing telemetry: never display zero degrees or falsely report off/actively heating.
- Timeout after command acceptance: show uncertainty and refresh, never resend power automatically.
- Second user/device and restart: reuse server config; expose no Sangens token to frontend.
- Hidden card, disabled motion and failed autoplay: stop video and preserve readable, usable controls.

## Task 1: Verify the login and response contract

**Files:** Create `docs/protocol.md`, `tests/fixtures/README.md`; update the spec only for evidence-backed changes.

**Interfaces:** Establish `DeviceSnapshot` fields, response nesting, IDs, authentication lifecycle and permitted user login. No product code until login feasibility is known.

- [ ] Trace `/email/send`, `/email/check`, `/auth/loginByEmail`, token/header handling and request headers in both decompilation and original disassembly. Record exact payloads and response nesting, including `emailToken`, CAPTCHA requirements and 409 handling.
- [ ] Inspect the official user login surface without submitting credentials. Do not use the admin login page, spoof CAPTCHA origins or extract application/browser credentials.
- [ ] Arrange the supported login step with the user through a local UI. User enters email/code directly; never ask for credentials in chat. If a legitimate HA-compatible login cannot be established, stop dependent deployment and report the exact obstacle; continue only independent offline work.
- [ ] Once login is available, GET devices/status only and compare temperatures/model with the official app. Produce manually sanitized fixtures excluding account details, serial, PIN and token. Mark synthetic fixtures explicitly if live data remain unavailable.
- [ ] Commit `docs: document verified Sangens protocol and authentication constraints` after reviewing the diff for private data.

## Task 2: Client, models and command rules

**Files:** Create `custom_components/sangens/api.py`, `models.py`, `const.py`, `tests/test_api.py`, `tests/test_models.py`, `pyproject.toml` and test fixtures; extend `.gitignore` for local environments/media/credentials.

**Interfaces:** `SangensClient(session, token)`, async `list_devices() -> list[DeviceSnapshot]`, `get_device(binding_id: str) -> DeviceSnapshot`, `set_power(microchip_id: str, enabled: bool) -> None`, `set_temperature(microchip_id: str, kind: str, value: float) -> None`, `set_mode(binding_id: str, mode_id: str) -> None`. Exceptions: `SangensAuthError`, `SangensConnectionError`, `SangensCommandUncertain`, `SangensProtocolError`. `DeviceSnapshot` is immutable and contains both IDs, connection/power/heater states, nullable measured/target temperatures and verified per-mode limits.

- [ ] Write failing tests for distinct IDs, `ON`/`off`, response nesting, null/malformed/unknown fields, non-finite/out-of-range temperatures, 401/403, 409, 429 and timeout. Assert one POST on timeout and no token in exception text.
- [ ] Run `python -m pytest tests/test_api.py tests/test_models.py -q`; verify failures are missing implementation, not fixture or environment errors.
- [ ] Implement the interfaces above with shared aiohttp session, TLS, bounded timeouts, explicit schema validation and no mutation retry. Distinguish power from actual heating. Do not log full responses or request bodies.
- [ ] Run the same tests; all pass. Commit `feat: add Sangens cloud client and validated device models`.

## Task 3: Shared HA configuration and coordinator

**Files:** Replace `custom_components/sangens/__init__.py`; create `config_flow.py`, `coordinator.py`, `entity.py`, `strings.json`, `translations/ru.json`, `translations/en.json`, `diagnostics.py`, `tests/test_config_flow.py`, `tests/test_coordinator.py`; update `manifest.json`.

**Interfaces:** `SangensCoordinator(hass, entry, client)` consumes Task 2, provides validated snapshots and `async_command(command, *, starts_heating: bool)`. Config flow stores one account token and selected binding IDs in the server entry. Platform entities consume coordinator snapshots, never direct HTTP.

- [ ] Write failing HA tests for one-time setup, duplicate prevention, second user reuse, restart/unload, reauthentication, redacted diagnostics, 30-second polling, error backoff, serial commands and zero writes on setup/reconnect. Separate selected-stove binding IDs from microchip IDs.
- [ ] Run `python -m pytest tests/test_config_flow.py tests/test_coordinator.py -q` and verify expected failures.
- [ ] Implement the verified Task 1 login flow, config entry lifecycle and platform forwarding. Never implement a fake successful auth step; expiration raises HA reauth. Register `cloud_polling`, version and config flow in manifest. Remove placeholder state creation.
- [ ] Implement coordinator availability, last successful update and confirmed state refresh after commands. Reject start on unavailable/invalid state; serialize commands without a pending background queue. Handle auth failure separately from transport failure.
- [ ] Run tests, validate translations and manifest, then commit `feat: add shared Sangens setup and coordinated updates`.

## Task 4: HA entities

**Files:** Create `climate.py`, `sensor.py`, `number.py`, `select.py`, `tests/test_entities.py`.

**Interfaces:** Climate exposes OFF/HEAT, current/target air temperature and heating action only when known; sensors expose present stone channels; number uses verified stone limits; select uses device-provided modes. All use coordinator command rules and stable unique IDs based on microchip identity.

- [ ] Write failing tests for unknown/offline state, selected stove targeting, unsupported stone channels, bounds from current mode, invalid options, target changes while off, and commands that must never start implicitly.
- [ ] Run `python -m pytest tests/test_entities.py -q`, confirm expected failures, then implement the four platforms with device grouping and meaningful Russian translations.
- [ ] Run entity and coordinator tests; verify registry uniqueness and unload/reload. Commit `feat: expose sauna temperatures modes and explicit power control`.

## Task 5: Shared card and local smoke

**Files:** Create `custom_components/sangens/frontend/sangens-card.js`, `frontend/sangens-card.test.mjs`, `examples/dashboard.yaml`, `docs/card.md`; add the supported HA static-resource registration to `__init__.py` with lifecycle tests.

**Interfaces:** `custom:sangens-card` accepts HA entity IDs and optional `smoke_url` only. Reads the HA state machine and calls HA services; contains no Sangens client or credential. All text data inserted using text nodes/properties, never unsanitized HTML. Media URLs limited to same-origin local resources.

- [ ] Write failing Node tests for confirmed on/off/unknown state rendering, separate power actions, confirmation on start, visibility and reduced-motion decisions, missing entities and unsafe URLs. Write HA test for resource registration without exposing protected config.
- [ ] Run `node --test frontend/sangens-card.test.mjs` and the HA resource test; verify expected failures.
- [ ] Implement responsive card: large temperatures, distinct state label, explicit start confirmation and immediate stop, advanced controls through HA entities. Add muted looping playsinline video with visibility/disconnect/reduced-motion cleanup and static fallback.
- [ ] Configure the shared dashboard once; serve confirmed smoke video from the home HA local directory. Do not commit proprietary media, account data or full household dashboard to GitHub.
- [ ] Run tests; inspect at 390px and desktop width, with on/off/unavailable simulated states. Confirm video stops and controls remain usable without animation. Commit `feat: add responsive sauna card with optional local smoke`.

## Task 6: Package, verify, install and document

**Files:** Update `README.md`, `hacs.json`, `.github/workflows/hassfest.yml`, `.github/workflows/hacs.yml`; create CI tests workflow and `docs/installation.md`. User-facing archive/report goes in the chat outputs folder, not in the repository.

**Interfaces:** HACS-compatible release layout, reproducible install/rollback instructions, explicit verified/unverified behavior and media setup.

- [ ] Run all Python and Node tests, compile/import checks and official hassfest/HACS checks. Fix only relevant failures and record exact versions/results. Review complete diff for credentials, proprietary binaries, network side effects and unsupported HA APIs.
- [ ] Commit `docs: document installation shared setup and verification`; push `codex/sangens-ha-control` and inspect CI outcomes. Do not claim CI passed while pending.
- [ ] Back up the existing server component/config entries and dashboard before changing them. Install the validated package using the existing authorized administration route, retaining a clear rollback. Do not retrieve the rejected Portainer admin key or weaken browser/certificate protections.
- [ ] Verify startup, one-time setup, temperatures against app and second-user access. No real heating test: report this limitation until a separate controlled test is explicitly arranged with the user.
- [ ] Deliver package, commit/branch links, checks and remaining limitations. If authentication blocks deployment, report a tested offline package as such, never as a working installed integration.
