# Assignment 3 — Mads-Opt

`starter_code/src/agentic_loop.py`의 `Agent(dispatcher).run()`이 진입점입니다.
**공식 starter 압축파일을 내려받지 못해 실제 인프라와의 통합 검증은 아직 하지 못했습니다.**
src 구현은 공개된 dispatcher 계약에 근거하며, 나머지 공식 파일은 설치 스크립트로 가져옵니다.

## 실행

```bash
# 저장소 루트
python3 scripts/install_official.py 3
python3 scripts/check_starter.py
cd assignment3/starter_code
bash evaluation_scripts/prepare_images.sh
export CS2680_API_KEY='본인의 수업 키'
export CS2680_MODEL_STANDARD=standard
export CS2680_MODEL_EXPERT=expert
export CS2680_MODEL_STARTER=starter
python3 evaluation_scripts/run_all.py --limit 0
python3 evaluation_scripts/run_all.py
```

`CS2680_BASE_URL`은 공식 runner가 container에 전달하는 egress proxy 주소를 사용합니다.
임의로 외부 API 주소를 하드코딩하지 않습니다. 모델 요청은 course proxy를 통해서만 나갑니다.
원본 sandbox.py와 sandbox_server.py는 설치 시 보존합니다.

## 구현한 최적화

| 선택 | 이유와 비용 |
|---|---|
| 기본 2개, 최대 5개 task worker | 서로 다른 task의 API·평가 대기를 겹침. 동시 실행 비용은 공유 budget으로 제한 |
| standard부터 시작, 재평가 실패/도구 오류 반복 시 expert | 비용 절감 가설. 실제 정확도 개선은 측정 전 |
| 최대 2회 평가 | 실패 task에 무한히 시간을 쓰지 않음. 어려운 task를 조기에 포기할 수 있음 |
| 읽기 결과 캐시 | 반복 읽기 감소. write/edit/bash 후 전체 캐시 무효화 |
| 연속 read/search만 병렬화 | write와 의존 순서를 보존하면서 독립 읽기를 겹침 |
| 6,000자 tool output, 65,000자 context | 입력 비용 감소. 긴 의존관계의 정보 손실 가능 |
| shared dollar budget | 입력 바이트 기반 보수적 예약 후 실제 usage로 정산. 공식 청구액과 동일함을 보장하지 않음 |

설정: `CS2680_WORKERS` (1–5), `CS2680_MAX_ATTEMPTS` (1–3),
`CS2680_HARNESS_BUDGET` (기본 $8). 공식 $10 상한에 여유를 두었습니다.
가격은 2026-10-18 과제 페이지 기준이며 `src/budget.py`에 명시했습니다.
실행 중 모델 청구/캐시 정책이 다르면 업데이트해야 합니다. 이 예산은 서버 과금을 막는 보증이 아닙니다.

`starter` tier 설정은 지원하지만 기본 정책은 사용하지 않습니다.
멀티에이전트 추론은 구현하지 않았고, task 및 읽기 도구의 병렬 실행을 구현했습니다.

## 공식 연동 확인 지점

- `Sandbox.exec(command)` → stdout/stderr/exit_code (또는 returncode) dict.
- `Sandbox.read_text(path)` → str, `write_text(path, text)`.
- `dispatcher.logger(k)`는 event별 method 또는 `log/emit(event, **fields)` 또는 `write(row)`.
- 실제 logger 인자가 다르면 `src/adapters.py`의 `dispatcher_sink`만 수정하세요.
- official dispatcher의 shutdown/동시성 동작은 실제 preflight 후 확인해야 합니다.

테스트용 dispatcher로 `next_task → patch → evaluate → continue → done`,
0개 테스트의 오판 방지, 예산 초과 전 요청 차단을 검증했습니다.
이 결과는 leaderboard 성공률이나 official logger 호환성의 증거가 아닙니다.

제출용으로는 `src/` 폴더만 zip에 담습니다. 원본 runtime을 수정한 경우 먼저
저장소 루트에서 `python3 scripts/sync_runtime.py`를 실행하세요.
실제 리더보드 제출, 학생 이름 설정, 세션 아카이브와 본인 작성 PDF·영상은 수행하지 않았습니다.

공식 명세: https://cs2680.com/assignments/assignment3
