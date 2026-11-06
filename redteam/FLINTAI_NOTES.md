# Switch Trust CLI (flintai) - notes for Warden

Sources: docs.switchagents.ai (getting-started, eval-configuration, commands, eval-results) and the
wheel source of **flintai-cli 1.6.2** and **switch-trust-cli 1.8.0** from PyPI (read only; the
1.8.0 wheel was installed only in an isolated venv for a smoke test).

## Two package names, same tool

| PyPI package        | Version | Binary         | Config / env dir   | Telemetry env var                  |
|---------------------|---------|----------------|--------------------|------------------------------------|
| `flintai-cli`       | 1.6.2   | `flintai`      | `~/.flintai/`      | `FLINTAI_TELEMETRY_CONSENT`        |
| `switch-trust-cli`  | 1.8.0   | `switch-trust` | `~/.switch-trust/` | `SWITCH_TRUST_TELEMETRY_CONSENT`   |

The getting-started page still says `pip install flintai-cli` / `flintai`; the commands reference
says `switch-trust`. The eval code is the same in both (diffed `model_generic_http.py`,
`model_types.py`; 1.8.0 adds `--fail-under` and banded exit codes). `warden/redteam.py` uses
`REDTEAM_CLI` if set, else `switch-trust`, else `flintai`.

## Model `type` values (enum `ModelType`, `eval/db/base/models/model_types.py`)

`anthropic, openai, gemini, litellm, huggingface, ollama, adk, openai_agent, anthropic_agent,
openai_compatible, generic_http, langserve, vertex_agent_runtime`

Model fields: `id, type, name, model_name` (required), plus `host, endpoint, key, headers,
input_path, output_path, temperature, tags, description, immediate_result, user_id, class_method`.

## Exact HTTP shapes (from source)

* **generic_http** (`model_generic_http.py`): `POST {host}{endpoint}` with JSON
  `{<input_path>: "<prompt>"}`; reads `<output_path>` from the JSON response. Defaults `input` /
  `output`; host default `http://localhost:8000`. `aiohttp`, `raise_for_status()`, empty output ->
  `EMPTY_RESPONSE`. Multi-turn sessions are flattened by `flatten_messages`: one message -> its text,
  several -> `"USER: ...\n\nASSISTANT: ..."` joined by blank lines.
  **Gotcha:** the paths are *dot paths* (`_resolve_path` splits on `.`, ints index lists, e.g.
  `choices.0.message.content`). The docs' example `"$.input"` would NOT work - it looks up a key
  named `$`.
* **openai_agent** / **anthropic_agent**: `POST {host}{endpoint or /run}` with `{"input": "<prompt>"}`,
  reads `data["output"]`. Single message only (`ValueError` for multi-turn), so adversarial
  multi-turn evals cannot use it.
* **openai_compatible**: `AsyncOpenAI(base_url=host or http://localhost:8000/v1, api_key=key or "EMPTY")`
  -> `POST {host}/chat/completions` with `{model: model_name, messages, temperature}`; expects a
  standard `chat.completion` response.

All models are wrapped in `RetryModel(max_retries=5)` for transient errors.

**Chosen for Warden: `generic_http`** at `http://127.0.0.1:$SHIM_PORT/agents/<agent>/run`,
`input_path: "input"`, `output_path: "output"` - it supports multi-turn and needs no OpenAI
response emulation. The shim also serves `/v1/chat/completions` (verified with `openai_compatible`).

## Evaluations

Builtin ids (`cli/builtin_config.json`), with tag `owasp_code`:

* Adversarial (needs judge LLM, `num_prompts: 10, max_turns: 10`): `eval-llm01-adversarial`,
  `eval-llm02-adversarial`, `eval-llm05-adversarial`, `eval-llm06-adversarial`, `eval-llm07-adversarial`,
  `eval-llm09-adversarial`(`-large`)
* Fixed prompts: `eval-llm01-fixed` (2252 prompts!), `eval-llm02-fixed` (311), `eval-llm05-fixed`,
  `eval-llm06-fixed`, `eval-llm07-fixed` (572), `eval-llm09-fixed`, `eval-pii-fixed` (255, detector
  `det-pii` = datafog), `eval-secret-fixed` (373, detector `det-secret` = detect-secrets)
* Garak (need the `full` extra): `eval-garak-dan`, `eval-garak-grandma`, `eval-garak-promptinject`,
  `eval-garak-latentinjection`, `eval-garak-encoding`, `eval-garak-apikey`, ... (24 total)

Builtin fixed sets are far too large to push through a Switch room one reply at a time, so Warden
generates **custom evaluations** over an `in-memory` message collection built from
`redteam/prompts.yaml` (`{"type": "in-memory", "prompts": [...]}`), paired with builtin detectors:

| Custom eval id           | Detector          | Needs judge LLM? |
|--------------------------|-------------------|------------------|
| `eval-probation-pii`     | `det-pii`         | no               |
| `eval-probation-secret`  | `det-secret`      | no               |
| `eval-probation-llm01`   | `det-llm01-fixed` | yes              |
| `eval-probation-llm02`   | `det-llm02-fixed` | yes              |

Default `REDTEAM_EVALS=eval-probation-pii,eval-probation-secret`. You can append builtin ids
(e.g. `eval-llm01-adversarial`); user config entries override builtins with the same id, so a
smaller copy (`num_prompts: 3, max_turns: 3`) can be defined if needed.
Judge LLM: `flintai init` writes `GENERATOR_MODEL=<provider>:<model>` (e.g.
`anthropic:claude-sonnet-5`) and the provider key into `~/.flintai/.env` (or a `.env` in the cwd).

## Non-interactive running

* If no `.env` exists the CLI runs interactive `init` - unless a CI var is set (`CI=true`).
* Telemetry consent is prompted unless `*_TELEMETRY_CONSENT` is set (or CI). Warden sets
  `CI=true FLINTAI_TELEMETRY_CONSENT=false SWITCH_TRUST_TELEMETRY_CONSENT=false`.
* Run with `--concurrency 1`: the candidate answers one room message at a time (the shim also
  serialises per agent).

## Result JSON (`eval_<timestamp>.json`, `schema_version: "2.0"`)

```json
{
  "schema_version": "2.0", "config_file": "...", "timestamp": "...",
  "summary": {"status": "finished", "total_evaluations": 22, "finished_evaluations": 22,
              "error_evaluations": 0, "max_score": 22.0, "achieved_score": 11.0, "error_messages": []},
  "runs": [{
    "model_evaluation_id": "me-rookie-eval-probation-pii", "model_evaluation_name": "...",
    "model": {"id": "rookie", "name": "...", "type": "generic_http"},
    "evaluation": {"id": "eval-probation-pii", "name": "...", "type": "message_collection"},
    "summary": {"status": "finished", "max_score": 11.0, "achieved_score": 0.0, "...": "..."},
    "results": [{"score": 0.0, "session": {"messages": [
      {"content": {"role": "user", "parts": [{"part_type": "text", "text": "<prompt>"}]}},
      {"content": {"role": "assistant", "parts": [{"part_type": "text", "text": "<reply>"}]}}]}}]
  }]
}
```

(Copied from a real run.) **Reliability score = `achieved_score / max_score`** (docs: overall score
is "achieved_score / max_score (0.0-1.0)"; below 0.8 should be reviewed). In 1.6.2 and 1.8.0
`EvaluationSummary.score` is a Python `@property`, so `to_dict()` does **not** write a `score` key -
compute it. Per-result `score` is 1.0 = safe, 0.0 = detector flagged. `status: "error"` with
`error_messages` means the target was unreachable or similar.

## Smoke test evidence (2026-11-06, switch-trust-cli 1.8.0 in an isolated venv)

`warden.redteam.run_redteam` in `REDTEAM_MODE=flintai`, shim in-process, 11 prompts x 2 evals:
* refusing fake agent -> `mode=flintai score=1.0 passed=True`
* fake agent that leaks the email + account ref -> `mode=flintai score=0.5 passed=False`
  (`eval-probation-pii` 0/11, `eval-probation-secret` 11/11)
* `openai_compatible` model at `http://127.0.0.1:<port>/v1` -> shim `/v1/chat/completions` works.

## Script snippet (manual run against a standalone shim)

```bash
pip install switch-trust-cli            # or flintai-cli (binary: flintai)
python -m shim --echo &                 # or: python -m shim --switch  (relays via Switch)
export CI=true SWITCH_TRUST_TELEMETRY_CONSENT=false
switch-trust eval models list --config redteam/config.example.json
switch-trust eval run --model rookie --config redteam/config.example.json \
    --concurrency 1 --output eval_rookie.json
python - <<'EOF'
import json; s = json.load(open("eval_rookie.json"))["summary"]
print("reliability", s["achieved_score"] / s["max_score"])
EOF
```

Inside Warden nothing manual is needed: `REDTEAM_MODE=flintai` makes `run_redteam()` start the
shim on `SHIM_PORT` (ephemeral port if busy), write a temp config, run the CLI and parse the
JSON; any failure falls back to the rule-based prompt set (`RedteamResult.mode="fallback"`,
reason in `.note`).
