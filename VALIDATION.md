# 구현 검증 기록

작성일: 2026-10-18. Python 3.12, Node 24 환경.

## 실제로 수행한 검증

- 과제 1: Python 서버 테스트 5개, JavaScript reducer 테스트 3개 통과.
- 과제 2–5: Python 테스트 25개 통과.
- 합성 ESS 4개: 실제 임시 파일에 대한 baseline unittest 실패 → scripted tool edit → unittest 통과.
- 자체 HTTP 테스트 서버: Chat Completions 요청, 401 fail-fast, SSE streaming/usage/TTFT 처리.
- 가짜 dispatcher: 실패 후 continue/evaluate/done, 0개 graded test의 성공 오판 방지.
- 버짓 초과 전 호출 차단, read cache 무효화, tool ID 대응, 중복 ID 거부, malformed JSON 복구,
  컨텍스트 쌍 보존, 경로·symlink 제한, 반복·iteration·token 종료.
- vLLM baseline 및 AWQ 명령의 dry-run, model allowlist/localhost 설정.

## 수행하지 못한 검증

- 실제 Claude Code 실행, 로그인 resume, 브라우저 시각 검증.
- 과제 2의 공식 qwen 모델, SWE-bench 및 실제 mytest의 모델 실행.
- 과제 3의 실제 course dispatcher/logger 및 leaderboard 실행.
- Docker 이미지 실행, GPU 모델 로딩, vLLM 실제 tool parsing, 정확도·latency 개선 측정.

이 환경에는 CS2680_API_KEY, Claude CLI, Docker, GPU, vLLM이 없습니다.
공식 starter 압축파일 다운로드도 HTTP 403으로 차단되었습니다.
4·5번 공식 상세 명세는 아직 공개되지 않았습니다.

테스트 통과는 런타임의 검증된 경로에 대한 근거이며 모델의 과제 해결률을 뜻하지 않습니다.
실험 결과, 학생이 직접 관찰해야 하는 내용, benchmark 점수를 만들어 넣지 않았습니다.
