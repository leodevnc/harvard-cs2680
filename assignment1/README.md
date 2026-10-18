# Mads-Lens — Assignment 1

Claude Code의 headless JSONL 출력을 브라우저로 실시간 전달하는 로컬 앱입니다.
에이전트 루프를 직접 구현하거나 Agent SDK를 사용하지 않습니다.

## 빠른 실행

macOS 또는 Linux, Python 3.10 이상이 필요합니다. Windows는 WSL에서 실행하세요.
Python 패키지 설치와 프론트엔드 빌드는 필요 없습니다.

```bash
cd cs2680/assignment1
python server.py
```

브라우저에서 http://127.0.0.1:8765 를 여세요. 기본값은 **합성 재생 데모**입니다.
재생은 입력한 요청을 실행하지 않으며 파일도 변경하지 않습니다.
데모에 표시되는 비용·시간·세션 ID는 합성값입니다.
실행 중인 도구, 실패한 도구, 서브에이전트 트리, 긴 결과 펼치기를 확인할 수 있습니다.
`실패 재생` 모드는 실패 상태를 보여줍니다.

## 실제 Claude Code 연결

1. Claude Code CLI를 공식 문서에 따라 설치하고 `claude`에서 계정 로그인을 완료하세요.
   수업 제출자는 수업에서 제공한 로그인을 사용하세요.
2. `claude --version`으로 PATH를 확인하세요.
3. 작업할 프로젝트 복사본을 지정해서 서버를 시작하세요.

```bash
python server.py --workspace ./demo_project
```

4. UI에서 `실제 Claude Code`를 선택하고 작업 폴더를 `.`으로 둔 뒤 요청하세요.

첫 요청 예시: `stats.py를 읽고 실패하는 테스트를 수정해줘. 서브에이전트로 먼저 조사해줘.`
후속 요청 예시: `방금 수정한 함수에 대한 설명을 README.md에 추가해줘.`
새 세션 버튼을 누르지 않으면 이전 session_id로 `--resume`합니다.
모드나 작업 폴더를 바꾸면 새 세션으로 전환됩니다. 새로고침 시 UI 대화는 초기화됩니다.

실제 명령은 다음과 같은 argv로 실행됩니다. shell 문자열 결합은 하지 않습니다.

```text
claude -p PROMPT --output-format stream-json --verbose
  --allowedTools Read,Glob,Grep,Edit,Write,Bash(python -m unittest*),Agent,Task
  [--resume SESSION_ID]
```

허용된 읽기·편집 도구와 unittest 명령은 자동 승인됩니다. 다른 명령은 CLI 설정에 따라
거절될 수 있으며, 해당 오류도 도구 결과로 표시됩니다. 이 허용 목록은 `server.py`의
`App.command()`에서 프로젝트에 맞게 바꿀 수 있습니다.
개인 API 계정으로 자동 과금되지 않도록 자식 프로세스에서는 `ANTHROPIC_API_KEY`를 제거합니다.
다른 provider를 설정한 CLI는 해당 설정을 따르므로 CLI 계정 설정을 확인하세요.

이 앱은 localhost 전용입니다. Host·Origin 확인과 사용자 정의 요청 헤더로 외부 웹페이지의
실행 요청을 차단합니다. 작업 폴더 선택은 `--workspace` 내부로 제한하지만 Claude CLI
자체를 OS 수준으로 격리하지는 않습니다. 실제 실행은 복사한 실습 프로젝트에서 하세요.
공개 서버 배포와 원격 접근은 지원하지 않습니다.

## 기능과 구조

| 공식 요구 기능 | 구현 위치/동작 |
|---|---|
| 프롬프트 및 작업 폴더 | POST `/api/run`, workspace 내부 폴더 선택 |
| 실시간 실행 과정 | subprocess stdout → NDJSON fetch 스트림, 텍스트·도구를 도착 즉시 렌더링 |
| 도구 결과 | tool_use ID와 tool_result ID 연결, 1,000자 미리보기와 전체 펼치기 |
| 실행 및 도구 상태 | pending/success/error/incomplete, running/finished/failed |
| 대화 이어가기 | session_id 저장 및 `--resume`, 폴더·모드 일치 확인 |
| 수치 표시 | result의 total_cost_usd, duration_ms, num_turns 표시 |
| 서브에이전트 트리 | parent_tool_use_id로 중첩, 접기, 넓은 화면의 도구 목차 |

추가 기능: 실행 중단, 15분 시간 제한, 동시 실행 방지, 연결 종료 오류,
새 세션, JSONL 다운로드, 서버 원본 스트림 보관.
Markdown은 HTML을 비활성화한 소규모 렌더러로 제목·목록·굵게·인라인 코드·코드 블록을 지원합니다.
완전한 CommonMark 구현은 아닙니다.

`total_cost_usd`는 CLI가 보고한 값을 그대로 표시합니다. CLI 버전에 따라 이어진
세션 전체의 누적 비용을 포함할 수 있으므로 두 실행의 표시 비용을 합산하지 마세요.

```text
server.py          로컬 HTTP, 프로세스, 스트리밍, 중단, JSONL 기록
static/model.js    도구 ID 및 부모 ID를 처리하는 순수 reducer
static/app.js      fetch 스트림, 화면, Markdown, 내보내기
static/style.css   반응형 UI
fixtures/         합성 성공·서브에이전트·실패 스트림
demo_project/     의도적으로 버그를 넣은 평균 계산 실습 코드
tests/            서버 통합 테스트와 reducer 테스트
```

실제/재생 이벤트는 `.runs/<uuid>.jsonl`에 저장합니다. 실제 이벤트에는 코드나 도구 출력이
들어갈 수 있어 기본적으로 git에서 제외했습니다. 수업 제출 때는 검토한 실제 세션만
별도 디렉터리로 복사해서 수업 지침에 따라 포함하세요. 이 파일은 Claude 원본 세션
아카이브를 대체하지 않습니다. 원본 세션도 CLI에서 별도로 내보내세요.

## 검증

```bash
python -m unittest discover -s tests -v
node --test tests/model.test.js
```

Node는 reducer 테스트에만 필요합니다. Python 서버 실행에는 필요 없습니다.
검증 환경에서 Python 서버 테스트 5개, JS reducer 테스트 3개가 통과했습니다.
실제 Claude CLI는 검증 환경에 설치되어 있지 않았습니다. 테스트용 CLI 프로세스로
stdout 실시간 수신, resume 인자, 동시 실행 거부, 타임아웃과 중단을 확인했습니다.
실제 계정 로그인·모델 실행과 브라우저 시각 검증은 별도 확인이 필요합니다.

실습 프로젝트 자체의 테스트는 의도적으로 실패합니다. 앱 테스트와 구분하세요.

## 실제 실행 확인 및 제출 체크

- 실제 Claude로 첫 요청과 문맥을 필요로 하는 후속 요청을 실행하세요.
- 실제 서브에이전트를 사용하여 트리와 목차를 확인하세요.
- 잘못된 작업 폴더를 입력해 오류 표시를 확인하세요.
- 2–3분 데모 영상을 녹화하고 직접 관찰한 내용을 `writeup.md`에 작성하세요.
- 수업에서 요구하는 원본 세션 아카이브, 비공개 저장소와 제출 절차를 따르세요.

프론트엔드를 Claude Code로 만들어야 한다는 공식 수행 조건은 이 작업에서 충족하지
않았습니다. 이 코드는 Codex로 작성한 학습용 구현입니다. 제출 전 해당 조건을
수업 정책에 맞게 직접 수행해야 합니다. 사용자의 실제 관찰이나 실행 결과를 만들어
넣지 않았으며, writeup은 질문만 담은 작성용 틀입니다.

출처: https://cs2680.com/assignments/assignment1
CLI 문서: https://code.claude.com/docs/en/headless
