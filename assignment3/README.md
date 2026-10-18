# Assignment 3 — Mads-Opt

The entry point is `Agent(dispatcher).run()` in `starter_code/src/agentic_loop.py`.
**Integration with the actual infrastructure remains unverified because the official starter archive could not be downloaded.**
The src implementation follows the public dispatcher contract; the installation script retrieves the remaining official files.

## Running the agent

```bash
# From the repository root
python3 scripts/install_official.py 3
python3 scripts/check_starter.py
cd assignment3/starter_code
bash evaluation_scripts/prepare_images.sh
export CS2680_API_KEY='your-course-key'
export CS2680_MODEL_STANDARD=standard
export CS2680_MODEL_EXPERT=expert
export CS2680_MODEL_STARTER=starter
python3 evaluation_scripts/run_all.py --limit 0
python3 evaluation_scripts/run_all.py
```

`CS2680_BASE_URL` uses the egress proxy address passed into the container by the official runner.
No arbitrary external API address is hardcoded. Model requests go through the course proxy only.
The original sandbox.py and sandbox_server.py are preserved during installation.

## Implemented optimizations

| Choice | Rationale and tradeoff |
|---|---|
| 2 task workers by default, up to 5 | Overlap API and evaluation waits across tasks; a shared budget limits concurrent spending |
| Start with standard, escalate to expert after a failed evaluation or repeated tool errors | Hypothesis for reducing cost; actual accuracy improvements have not been measured |
| At most 2 evaluations by default | Avoid spending unlimited time on failing tasks; difficult tasks may be abandoned early |
| Read-result cache | Reduce repeated reads; invalidate the entire cache after write/edit/bash |
| Parallelize consecutive read/search calls only | Overlap independent reads while preserving write ordering and dependencies |
| 6,000-character tool output and 65,000-character context | Reduce input cost; information about long dependencies may be lost |
| Shared dollar budget | Reserve conservatively using input bytes, then reconcile with actual usage; not guaranteed to match official billing |

Settings: `CS2680_WORKERS` (1–5), `CS2680_MAX_ATTEMPTS` (1–3), and
`CS2680_HARNESS_BUDGET` (default $8, leaving room below the official $10 limit).
Prices in `src/budget.py` are based on the assignment page as of 2026-10-18.
Update them if model billing or caching policies differ at runtime. This budget does not guarantee
a cap on server-side charges.

Configuration supports the `starter` tier, but the default policy does not use it.
The implementation parallelizes tasks and read tools; it does not implement multi-agent reasoning.

## Official integration checks

- `Sandbox.exec(command)` → a dictionary with stdout/stderr/exit_code (or returncode).
- `Sandbox.read_text(path)` → str; `write_text(path, text)`.
- `dispatcher.logger(k)` supports event-specific methods, `log/emit(event, **fields)`, or `write(row)`.
- If the actual logger arguments differ, update `dispatcher_sink` in `src/adapters.py`.
- Verify the official dispatcher's shutdown and concurrency behavior in a real preflight run.

A test dispatcher verified `next_task → patch → evaluate → continue → done`, prevention of false
success with zero tests, and request blocking before exceeding the budget. These results do not
establish leaderboard success rates or compatibility with the official logger.

For submission, include only the `src/` folder in the zip. If you change the canonical runtime,
first run `python3 scripts/sync_runtime.py` from the repository root.
Leaderboard submission, student name configuration, session archives, and your own PDF and video
have not been completed.

Official specification: https://cs2680.com/assignments/assignment3
