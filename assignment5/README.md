# Assignment 5 — Mads-Stack (Preliminary Implementation)

**Detailed specifications are scheduled for release on 2026-11-11.** The current implementation
provides a reproducible experiment runner and serving profiles based on the public overview.
No actual performance gains have been measured yet.

## Baseline experiment

Start the Assignment 4 baseline server first. From the repository root:

```bash
python3 assignment5/experiment.py \
  --tasks assignment5/workloads/ess.json \
  --agent-config assignment4/configs/agent.json \
  --serving-config assignment4/configs/baseline.json \
  --hypothesis 'Baseline: measure accuracy and runtime on the fixed ESS examples without caching.' \
  --concurrency 1 --repeats 3 --output results/baseline
```

This runs the actual model, so the GPU endpoint must be ready. Each task starts in a temporary copy.
If the source is a git repository, the committed snapshot is cloned; uncommitted changes are excluded.
Use practice projects without symlinks or secret files. Existing output directories are not overwritten.

The hypothesis, workload hash, source hash, and settings are saved before any model calls.
Changes to evaluation `protected_files` are detected and reverted before running tests.
A task is not counted as solved if tests fail, even when the model calls `done`.
Tasks already passing at baseline are not counted as newly solved.
This verifier is for local experiments and does not replace the official SWE-bench grader.

## Optimization experiment

Stop the baseline server and start this profile:

```bash
python3 assignment4/serve.py --config assignment5/configs/prefix_batch.json
```

Use the same tasks and number of repetitions:

```bash
python3 assignment5/experiment.py \
  --tasks assignment5/workloads/ess.json \
  --agent-config assignment5/configs/optimized_agent.json \
  --serving-config assignment5/configs/prefix_batch.json \
  --hypothesis 'Shared-prefix caching and parallel reads reduce wall time and input volume while preserving solved tasks.' \
  --concurrency 4 --repeats 3 --output results/optimized
python3 assignment5/compare.py results/baseline results/optimized --output results/comparison.json
```

This example changes several variables at once. To identify each contribution, also run separate
experiments changing only prefix caching, only concurrency, and only context/output caps.
AWQ has a separate `configs/awq.json` profile. Measure both memory savings and accuracy loss.
Speculative decoding is not included in this implementation.

## Measurements

```bash
python3 assignment5/profile_server.py \
  --prompts assignment5/workloads/prompts.json \
  --concurrency 4 --output results/serving-profile.json
```

- TTFT: time until the first actual content/tool/reasoning delta arrives; role-only chunks are excluded.
- TPOT: elapsed time from first content to completion / (completion tokens − 1). This includes some delivery time for final usage/framing.
- Output throughput: total completion tokens / total host wall time.
- Agent metrics: API/tool time, token usage, retries, context compaction, cache hits, and tool errors.
- Comparison: requires matching workload, source, and repetition counts; computes per-task regressions and wall time per success.

Inspect GPU utilization and VRAM with `nvidia-smi`, and server queues and KV cache with vLLM `/metrics`.
The runner does not automatically collect GPU hardware telemetry. Warmup exclusion and cache flushing
are not automatic; control and record them yourself. Also verify that the serving configuration file
matches the running server's actual settings.

`workloads/ess.json` contains synthetic educational examples. It is not presented as data satisfying
Assignment 2's requirement for four real mytest issues. Assessing generalization requires real problems
and a separate holdout set.
