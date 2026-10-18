# Assignment 2 — Mads-Loop

공식 CLI와 로그 스키마를 따르는 자체 코딩 에이전트입니다. Python 3.10+ 표준 라이브러리만
사용합니다. 모델은 기본값 `qwen3.6-35b-a3b`, endpoint는 수업 프록시입니다.

## 실행

```bash
# 저장소 루트에서 공식 인프라 설치
python3 scripts/install_official.py 2
cd assignment2
export CS2680_API_KEY='본인의 수업 키'
python3 madsLoop.py -p '설명한 문제를 해결해줘' --log /path/to/repo
```

로컬 기본 실행은 파일 도구만 허용합니다. 임의 셸 명령 실행은 명시적으로
`--allow-shell`을 줘야 하며, 실제 과제는 disposable task container에서 실행하세요.
`cwd` 지정은 OS sandbox가 아닙니다. 공식 이미지에 파일·테스트 의존성을 갖춰 두어야 합니다.

```bash
export MADSLOOP_REPO="$PWD"
bash evaluation_scripts/run_task.sh 0
python3 evaluation_scripts/make_patches.py
bash evaluation_scripts/evaluate.sh
# 또는 설치된 공식 전체 평가
bash evaluation_scripts/run_all.sh
```

`run_task.sh`는 이 구현의 `run_task.py`를 실행합니다. task JSON에서 공개 문제 설명만 가져와
container에 전달합니다. agent source와 출력 폴더만 마운트하고 평가용 `task_test.json`,
gold diff는 마운트하지 않습니다. 실패 시에도 로그와 가능한 partial diff를 회수합니다.
`git add -N`으로 새 production 파일도 diff에 포함하며 commit은 만들지 않습니다.
Apple Silicon에서는 공식 안내대로 `PLATFORM_FLAG='--platform linux/amd64'`를 설정하세요.

## 런타임

- `client.py`: OpenAI-compatible HTTP 요청, 인증 오류 즉시 종료, 429/5xx·연결 오류 재시도.
- `tools.py`: read/search/exact edit/new file/bash/done의 JSON schema와 인자 검증.
- `runtime.py`: assistant/tool ID 쌍 유지, 출력 축약, 완전한 turn 단위 컨텍스트 정리,
  반복 호출 탐지, 토큰·iteration·시간 제한.
- `trace.py`: `run_start/api_request/api_retry/tool_call/tool_result/run_end`의 정확한 필드 검증.

추가 측정값은 `--metrics metrics.json`으로 별도 저장하므로 공식 trace 필드를 변경하지 않습니다.
컨텍스트 크기는 tokenizer를 설치하지 않는 설계상 문자 수 기준입니다. 실제 토큰 사용량은
API `usage`를 그대로 기록합니다. 모델이 usage를 주지 않으면 0으로 꾸미지 않고 종료합니다.
시간 제한은 iteration/retry 경계에서 확인하며, 이미 실행 중인 네트워크·tool 요청에는 각각의
timeout이 적용됩니다. 엄격한 전체 wall-clock 상한은 외부 container runner에서 강제해야 합니다.

루프의 `done`은 모델이 종료를 요청했다는 뜻입니다. 문제 해결 성공 여부는 공식 평가가 결정합니다.

## 공식 mytest

`mytest/verify.py`와 `verify.sh`는 fresh container에서 patch를 적용하고 테스트를 검증합니다.
본인의 실제 프로젝트 또는 출처가 확인된 실제 오픈소스 이슈를 준비해야 합니다.
합성 ESS 예제를 공식 mytest로 가장하지 않았습니다.

필요한 데이터:

- `mytest/tasks.json`: instance_id별 `docker_image`, `base_commit`, `problem_statement`,
  빈 `requirements`와 `interface`.
- `mytest/task_test.json`: 공식 4필드와 이 verifier용 `test_command` argv,
  `junit_path` 절대 경로. JUnit 이름은 `classname::name`을 사용합니다.
- 과제별 Dockerfile과 gold.diff, 실제 실행 전후 로그.

예시 테스트 명령은 `['python3','-m','pytest','tests/test_feature.py','--junitxml=/tmp/results.xml']`,
`junit_path`는 `/tmp/results.xml`입니다. pytest는 해당 task 이미지에 미리 설치해야 합니다.

```bash
bash mytest/verify.sh actual_issue_id
bash mytest/verify.sh actual_issue_id mytest/tasks/actual_issue_id/gold.diff
```

검증기는 누락되거나 skipped인 테스트를 통과로 처리하지 않습니다. diff를 적용한 후
선택된 기존 테스트를 HEAD로 복원합니다. 테스트 명령은 준비한 명세대로만 실행됩니다.
실제 모델 평가 없이 `solved_after_change`와 `unsolved` 분류를 임의로 채우지 않았습니다.
이 데이터와 실행 근거, 직접 작성해야 하는 PDF와 영상은 남은 제출 작업입니다.

공식 명세: https://cs2680.com/assignments/assignment2
