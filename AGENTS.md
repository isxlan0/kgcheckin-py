# Repository Guidelines

## Project Structure & Module Organization
This repository is now a Python-only project. Runtime code lives under `src/kugou_signer/`, split by responsibility: `accounts/` manages local account records, `config/` handles `config.toml` and `accounts.json`, `kugou/` contains request, signature, and crypto code, `scheduler/` computes the next run and countdown output, and `services/` orchestrates the sign-in flow. Tests live in `tests/`. Generated local data belongs in `config/` and `data/` and should not be committed.

## Build, Test, and Development Commands
- `python -m venv .venv` then `.venv\Scripts\activate`: create and activate a local environment.
- `pip install -r requirements.txt`: install runtime dependencies for local development.
- `python main.py`: launch the interactive console directly from the repo root without installing.
- `python main.py run`: start the daemon-style countdown and scheduled sign-in loop.
- `python main.py schedule set --time 00:01 --jitter-seconds 30`: set the daily run time and symmetric random jitter.
- `python main.py settings set --account-gap-min-seconds 5 --account-gap-max-seconds 15 --vip-ad-gap-min-seconds 25 --vip-ad-gap-max-seconds 35`: update per-account and per-ad delay ranges.
- `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v`: run the current unit test suite.

## Coding Style & Naming Conventions
Use 4-space indentation, type hints on public functions, and clear module boundaries. Keep CLI and storage messages in readable Chinese. Prefer `snake_case` for functions, variables, files, and JSON keys such as `user_id` and `last_run_at`. Keep crypto and request helpers isolated in `kugou/`; do not mix network details into scheduler or storage modules.

## Testing Guidelines
Every change that touches crypto, request signing, config parsing, or scheduling should include or update a unit test. Reuse deterministic vectors when validating JS-to-Python compatibility. For behavior changes, test both the happy path and one failure path, for example invalid config, migrated legacy account data, or schedule rollover to the next day.

## Commit & Pull Request Guidelines
Use short, behavior-focused commit subjects, preferably concise Chinese phrases consistent with the existing history. Pull requests should describe the user-visible change, list the commands used for verification, and call out any config or data format changes. Do not commit real phone numbers, tokens, generated QR images, or local `config/config.toml` and `data/accounts.json` files.
