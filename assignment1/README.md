# Mads-Lens — Assignment 1

A local app that streams Claude Code's headless JSONL output to the browser in real time.
It does not implement its own agent loop or use the Agent SDK.

## Quick start

Requires macOS or Linux and Python 3.10+. On Windows, use WSL.
No Python package installation or frontend build is required.

```bash
cd harvard-cs2680/assignment1
python server.py
```

Open http://127.0.0.1:8765 in your browser. The default mode is a **synthetic replay demo**.
Replay does not execute your prompt or modify files. Displayed costs, durations, and session IDs
are synthetic. You can inspect running tools, failed tools, the subagent tree, and expandable
long outputs. The failure replay option (`failure`) demonstrates error states.

## Connecting to live Claude Code

1. Install the Claude Code CLI using the official documentation and sign in through `claude`.
   Students submitting coursework should use the course-provided login.
2. Check your PATH with `claude --version`.
3. Start the server with a copy of the project you want to work on.

```bash
python server.py --workspace ./demo_project
```

4. Select the live Claude Code option (`live`) in the UI, keep the working directory at `.`, and enter a prompt.

Example first prompt: `Read stats.py and fix the failing tests. Use a subagent to investigate first.`
Example follow-up: `Add an explanation of the function you just fixed to README.md.`
Unless you start a new session, subsequent requests use `--resume` with the previous session_id.
Changing the mode or working directory starts a new session. Refreshing the page clears the UI conversation.

The actual command uses the following argument vector, without shell string concatenation:

```text
claude -p PROMPT --output-format stream-json --verbose
  --allowedTools Read,Glob,Grep,Edit,Write,Bash(python -m unittest*),Agent,Task
  [--resume SESSION_ID]
```

Allowlisted read/edit tools and unittest commands are approved automatically. Other commands may be
rejected depending on CLI settings; those errors also appear in tool results. Customize the allowlist
for your project in `App.command()` in `server.py`.
The child process removes `ANTHROPIC_API_KEY` to avoid automatically billing a personal API account.
If your CLI is configured for another provider, it follows that configuration; check your CLI account settings.

This app is for localhost use only. Host and Origin checks plus a custom request header block execution
requests from external web pages. Working directories must be inside `--workspace`, but the Claude CLI
itself is not isolated at the OS level. Use a copied practice project for live runs.
Public server deployment and remote access are not supported.

## Features and structure

| Required feature | Implementation or behavior |
|---|---|
| Prompt and working directory | POST `/api/run`, directory selection within the workspace |
| Live execution view | Subprocess stdout → NDJSON fetch stream; text and tools render as they arrive |
| Tool results | Match tool_use and tool_result IDs; 1,000-character previews with expandable full output |
| Run and tool status | pending/success/error/incomplete, running/finished/failed |
| Conversation continuity | Store session_id and use `--resume`; check matching directory and mode |
| Metrics | Display total_cost_usd, duration_ms, and num_turns from the result |
| Subagent tree | Nest by parent_tool_use_id, collapsible branches, tool outline on wide screens |

Additional features include stopping runs, a 15-minute timeout, concurrent-run prevention,
connection-loss errors, new sessions, JSONL downloads, and server-side raw stream archives.
A small Markdown renderer supports headings, lists, bold text, inline code, and code blocks with HTML disabled.
It is not a full CommonMark implementation.

`total_cost_usd` is displayed exactly as reported by the CLI. Depending on the CLI version, it may include
the cumulative cost of a resumed session, so do not add the displayed costs of two runs together.

```text
server.py         Local HTTP, processes, streaming, cancellation, JSONL recording
static/model.js   Pure reducer for tool IDs and parent IDs
static/app.js     Fetch streams, UI, Markdown, export
static/style.css  Responsive UI
fixtures/         Synthetic success, subagent, and failure streams
demo_project/     Practice code with an intentionally buggy mean calculation
tests/            Server integration tests and reducer tests
```

Live and replay events are saved to `.runs/<uuid>.jsonl`. Live events may contain code or tool output,
so these files are excluded from git by default. For course submission, copy only reviewed live sessions
to a separate directory and include them according to course instructions. These files do not replace
the original Claude session archives; export those separately from the CLI.

## Validation

```bash
python -m unittest discover -s tests -v
node --test tests/model.test.js
```

Node is required only for reducer tests, not for running the Python server.
In the validation environment, 5 Python server tests and 3 JS reducer tests passed.
The actual Claude CLI was not installed. A test CLI process verified live stdout delivery, resume
arguments, concurrent-run rejection, timeouts, and cancellation. Real account authentication,
model execution, and browser visual checks still need verification.

The practice project's own tests intentionally fail. They are separate from the app tests.

## Live-run and submission checklist

- Run an initial prompt and a follow-up that requires context using live Claude.
- Use a real subagent and inspect the tree and outline.
- Enter an invalid working directory and check the error display.
- Record a 2–3 minute demo video and write your own observations in `writeup.md`.
- Follow course instructions for original session archives, the private repository, and submission.

The official requirement to build the frontend with Claude Code was not fulfilled in this work.
This is an educational implementation written with Codex. Before submitting, complete that requirement
yourself in accordance with course policy. No user observations or execution results have been invented;
the writeup contains only prompts for your own report.

Source: https://cs2680.com/assignments/assignment1
CLI documentation: https://code.claude.com/docs/en/headless
