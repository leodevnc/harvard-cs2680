# Harvard CS2680 — Agents and Model Serving

Educational Python implementations based on the public [CS2680](https://cs2680.com/) assignments.
**Implemented code does not mean a completed official submission.** Live model evaluations,
student observation reports, videos, and leaderboard submissions have not been completed.
Status as of **2026-10-18**.

| Assignment | Implementation | Validation status |
|---|---|---|
| [1 · Mads-Lens](assignment1/README.md) | Claude Code streaming web UI, tool tree, resume, replay | 5 server tests and 3 JS tests passed. Live Claude and browser behavior unverified |
| [2 · Mads-Loop](assignment2/README.md) | Custom agent loop, tools, context management, retries, logging, Docker patch runner | Synthetic responses, actual file edits, and error handling verified. Official model and SWE-bench not run |
| [3 · Mads-Opt](assignment3/README.md) | Dispatcher adapter, up to 5 task workers, parallel reads, model switching, budget limits | Contract tests with a fake dispatcher. Official starter integration still needs verification |
| [4 · Mads-Serve](assignment4/README.md) | Self-hosted Qwen2.5 7B with vLLM, tool-call checks, local agent | Preliminary implementation based on the public overview. Docker/GPU execution unverified |
| [5 · Mads-Stack](assignment5/README.md) | Prefix caching, batching, AWQ profiles, experiment records, protected tests, TTFT/TPOT measurements, comparisons | Preliminary implementation based on the public overview. No live model performance results |

Detailed specifications are scheduled for October 21 for Assignment 4 and November 11 for Assignment 5.
These implementations are not claimed to be fully compliant submissions for those assignments.
Where the assignment index and individual pages differed, Assignments 2 and 3 follow the latest
requirements on their individual pages.

## One-minute offline quick start

Requires Python 3.10+ and Node.js 18+ (only for Assignment 1 JS tests).
The core code requires no pip installation.

```bash
git clone https://github.com/leodevnc/harvard-cs2680.git
cd harvard-cs2680
python3 -m unittest discover -s tests -v
python3 scripts/offline_demo.py
python3 scripts/sync_runtime.py --check
```

The offline examples cover four small bugs: SOC clamping, power-to-energy conversion,
discharge efficiency, and weighted rack SOC. **Model responses are scripted synthetic data.**
The demo verifies actual temporary file edits and before/after unittest results; it does not
measure model accuracy.

Assignment 1 UI:

```bash
cd assignment1
python3 server.py
```

Open http://127.0.0.1:8765. Synthetic stream replay is the default mode.

## Installing the official starters

Downloads of the cs2680.com archives were blocked with HTTP 403 in this environment.
The official evaluation infrastructure and task data have not been recreated or inferred.
These commands install only missing official files and preserve the implementation files:

```bash
python3 scripts/install_official.py 2
python3 scripts/install_official.py 3
python3 scripts/check_starter.py
```

You can also use archives downloaded separately:

```bash
python3 scripts/install_official.py 2 --archive /path/to/assignment2.tar.gz
python3 scripts/install_official.py 3 --archive /path/to/assignment3.tar.gz
```

Compare the Sandbox and trace logger argument formats in Assignment 3's `src/adapters.py`
with the installed official code. Current tests check a contract derived from public documentation;
they do not establish official starter compatibility. Unsupported logger formats raise an error
rather than being silently ignored.

## Requirements for live runs

- Assignment 1: Claude Code CLI and an authenticated account.
- Assignments 2 and 3: course `CS2680_API_KEY`, Docker, official starters, and evaluation images.
- Assignments 4 and 5: NVIDIA GPU, NVIDIA Container Toolkit, Docker, and space for model downloads.
- Assignment 2: four `mytest` cases based on real past project or open-source issues, with evidence from model runs before and after changes.
- Each assignment: real session archives, your own report, and a video.

Keep secret keys in environment variables, out of the repository.
The course requires a private repository for submission. This repository's visibility has not been changed.
Official data, evaluation infrastructure, and execution logs are ignored by git by default.

## Structure and validation

The canonical shared runtime is in `assignment2/src/mads/`. Because Assignment 3 submits only
`src/`, the same code is copied to `assignment3/starter_code/src/mads/`. After editing the runtime,
run `python3 scripts/sync_runtime.py`; CI checks that the copies match.

```bash
# Repository root: Assignment 2–5 tests
python3 -m unittest discover -s tests -v
# Assignment 1
cd assignment1
python3 -m unittest discover -s tests -v
node --test tests/model.test.js
```

See [VALIDATION.md](VALIDATION.md) for validation results and limitations.
This implementation was written with OpenAI Codex. No personal student observations or live LLM/GPU
results have been fabricated. Submission reports for Assignments 2 and 3, which prohibit AI-written
reports, have not been generated.

## Sources

- https://cs2680.com/assignments/assignment1
- https://cs2680.com/assignments/assignment2
- https://cs2680.com/assignments/assignment3
- https://cs2680.com/assignments/
- https://cs2680.com/to_release
- https://docs.vllm.ai/en/latest/features/tool_calling/
- https://huggingface.co/Qwen/Qwen2.5-7B-Instruct
