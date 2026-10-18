# Assignment 4 — Mads-Serve (Preliminary Implementation)

**Detailed specifications had not been released as of 2026-10-18.** The official release date is October 21.
Qwen2.5-7B-Instruct was selected based on the public overview's requirement to self-host a 7–8B
open-weight model. There is no commercial API fallback or automatic switch to a larger model.

## Getting started

Requires Linux, Docker, an NVIDIA GPU, and NVIDIA Container Toolkit.
GPU VRAM requirements depend on context length, concurrent requests, and dtype. If you run out of
memory, reduce concurrency and max-model-len, or experiment separately with the AWQ profile.
GPU execution has not been tested in this environment.

```bash
# From the repository root
python3 assignment4/serve.py --dry-run
python3 assignment4/serve.py
```

In a separate terminal:

```bash
python3 assignment4/check_endpoint.py
python3 assignment4/run_agent.py \
  -p 'Fix the bug in battery.py where negative SOC is not clamped to zero' \
  assignment5/workloads/ess/soc_clamp
```

This command actually modifies the example files. For comparative experiments, use the Assignment 5
runner to edit and evaluate independent temporary copies. Use `--allow-shell` only in disposable
environments; the small examples can run with file-editing tools alone.
For a remote GPU, use an SSH tunnel to localhost:8000. To reduce accidental use of a commercial endpoint,
`run_agent.py` accepts only loopback addresses.

## Choices and observations

- The vLLM image is pinned to `v0.11.0`; this is not a claim that it is the latest version.
- `--enable-auto-tool-choice --tool-call-parser hermes` matches the model's Hermes-style tool template.
- 16K context, 8 sequences by default, and prefix caching disabled in the baseline.
- `check_endpoint.py` checks only whether actual structured tool_calls are returned; it does not execute tools.
- `configs/agent.json` reduces tool output and context for the small model and disables parallel reads.

Assess model output quality, accuracy degradation, and recovery using actual evaluations on the same
workload. No measurements are available yet. The Assignment 5 comparison runner can compare frontier
baseline results with self-hosted results. The serving configuration records the supplied settings;
it does not automatically verify the running server's actual configuration.

Sources:

- https://cs2680.com/assignments/
- https://cs2680.com/to_release
- https://docs.vllm.ai/en/latest/features/tool_calling/
- https://huggingface.co/Qwen/Qwen2.5-7B-Instruct
