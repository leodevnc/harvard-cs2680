# Assignment 2 — Mads-Loop

A custom coding agent that follows the official CLI and log schema. It uses only the Python 3.10+
standard library. The default model is `qwen3.6-35b-a3b`, accessed through the course proxy.

## Running the agent

```bash
# Install the official infrastructure from the repository root
python3 scripts/install_official.py 2
cd assignment2
export CS2680_API_KEY='your-course-key'
python3 madsLoop.py -p 'Fix the described problem' --log /path/to/repo
```

Local runs allow only file tools by default. Arbitrary shell commands require an explicit
`--allow-shell` flag. Run actual assignment tasks in disposable task containers.
Setting `cwd` does not provide an OS sandbox. The official image must contain the required files
and test dependencies.

```bash
export MADSLOOP_REPO="$PWD"
bash evaluation_scripts/run_task.sh 0
python3 evaluation_scripts/make_patches.py
bash evaluation_scripts/evaluate.sh
# Or run the installed official full evaluation
bash evaluation_scripts/run_all.sh
```

`run_task.sh` invokes this implementation's `run_task.py`. It extracts only the public problem
description from the task JSON and passes it to the container. It mounts the agent source and output
directory, but not the evaluation `task_test.json` or gold diff. Logs and any available partial diff
are collected even after failure. `git add -N` includes new production files in the diff without
creating a commit. On Apple Silicon, set `PLATFORM_FLAG='--platform linux/amd64'` as instructed by the course.

## Runtime

- `client.py`: OpenAI-compatible HTTP requests, immediate failure on authentication errors, and retries for HTTP 429/5xx and connection errors.
- `tools.py`: JSON schemas and argument validation for read/search/exact edit/new file/bash/done.
- `runtime.py`: assistant/tool ID pairing, output truncation, context compaction by complete turns, repeated-call detection, and token/iteration/time limits.
- `trace.py`: exact field validation for `run_start/api_request/api_retry/tool_call/tool_result/run_end`.

Additional metrics are stored separately with `--metrics metrics.json`, preserving the official trace fields.
Context size is measured in characters because the implementation does not install a tokenizer.
Actual token usage is recorded from API `usage`. If usage is missing, execution stops instead of
reporting a fabricated zero. Time limits are checked at iteration and retry boundaries; network and
tool calls already in progress have their own timeouts. A strict overall wall-clock limit must be
enforced by an external container runner.

The loop's `done` means the model requested termination. The official evaluation determines whether
the problem was solved.

## Official mytest cases

`mytest/verify.py` and `verify.sh` apply patches and verify tests in fresh containers.
You must supply real issues from your own projects or verifiable open-source projects.
The synthetic ESS examples are not presented as official mytest cases.

Required data:

- `mytest/tasks.json`: `docker_image`, `base_commit`, `problem_statement`, and empty `requirements` and `interface` for each instance_id.
- `mytest/task_test.json`: the four official fields plus this verifier's `test_command` argument vector and absolute `junit_path`. JUnit test identities use `classname::name`.
- A Dockerfile and gold.diff for each task, plus logs from actual before/after runs.

Example test command: `['python3','-m','pytest','tests/test_feature.py','--junitxml=/tmp/results.xml']`,
with `junit_path` set to `/tmp/results.xml`. Install pytest in the task image beforehand.

```bash
bash mytest/verify.sh actual_issue_id
bash mytest/verify.sh actual_issue_id mytest/tasks/actual_issue_id/gold.diff
```

The verifier does not count missing or skipped tests as passing. After applying the diff, it restores
the selected existing tests to HEAD. Test commands run only as specified in the prepared metadata.
The `solved_after_change` and `unsolved` classifications have not been filled in without actual model
evaluation. Preparing these data and execution records, writing your own PDF, and recording a video
remain necessary for submission.

Official specification: https://cs2680.com/assignments/assignment2
