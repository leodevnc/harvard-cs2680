# Harvard CS2680 — 에이전트와 서빙 실습

[CS2680](https://cs2680.com/) 공개 과제를 바탕으로 만든 Python 학습용 구현입니다.
**코드 구현과 공식 과제 제출 완료는 다릅니다.** 실제 모델 평가·학생 관찰 보고서·영상·
리더보드 제출은 수행하지 않았습니다. 작성 기준일: **2026-10-18**.

| 과제 | 구현 | 검증 상태 |
|---|---|---|
| [1 · Mads-Lens](assignment1/README.md) | Claude Code 스트림 웹 UI, 도구 트리, resume, replay | 서버 5개 + JS 3개 테스트 통과. 실제 Claude/브라우저 미검증 |
| [2 · Mads-Loop](assignment2/README.md) | 자체 에이전트 루프, 도구, 컨텍스트, 재시도, 로그, Docker patch runner | 합성 응답·실제 파일 수정·오류 처리 검증. 공식 모델/SWE-bench 미실행 |
| [3 · Mads-Opt](assignment3/README.md) | dispatcher 연동 어댑터, 최대 5개 task worker, 읽기 병렬화, 모델 전환, 비용 제한 | 가짜 dispatcher로 계약 테스트. 공식 starter 연동은 추가 확인 필요 |
| [4 · Mads-Serve](assignment4/README.md) | Qwen2.5 7B + vLLM 자체 서빙, 도구 호출 점검, 로컬 에이전트 | 공개 개요 기반 선행 구현. Docker/GPU 실행 미검증 |
| [5 · Mads-Stack](assignment5/README.md) | prefix cache·배칭·AWQ 설정, 실험 기록, 보호된 테스트, TTFT/TPOT 측정, 비교 | 공개 개요 기반 선행 구현. 실모델 성능 결과 없음 |

4번 상세 명세는 10월 21일, 5번은 11월 11일 공개 예정입니다.
현재 4·5번을 공식 명세에 완전히 부합하는 제출물이라고 주장하지 않습니다.
과제 목록 페이지와 개별 페이지가 다를 경우 2·3번은 개별 페이지의 최신 요구사항을 따랐습니다.

## 1분 오프라인 실행

Python 3.10+, Node.js 18+ (과제 1 JS 테스트에만 필요). 기본 코드에는 pip 설치가 필요 없습니다.

```bash
git clone https://github.com/leodevnc/harvard-cs2680.git
cd harvard-cs2680
python3 -m unittest discover -s tests -v
python3 scripts/offline_demo.py
python3 scripts/sync_runtime.py --check
```

오프라인 예제는 SOC 클램프, 전력·에너지 단위, 방전 효율, 랙별 가중 SOC의 네 가지
작은 버그를 다룹니다. **모델 응답은 스크립트로 지정한 합성 데이터**입니다.
실제 임시 파일 수정과 전후 unittest 결과는 검증하지만 모델 정확도는 측정하지 않습니다.

과제 1 UI:

```bash
cd assignment1
python3 server.py
```

http://127.0.0.1:8765 에 접속합니다. 기본값은 합성 스트림 재생입니다.

## 공식 starter 설치

이 환경에서는 cs2680.com의 압축파일 다운로드가 HTTP 403으로 차단되었습니다.
공식 평가 인프라와 과제 데이터는 복제하거나 추정해서 만들지 않았습니다.
다음 명령은 누락된 공식 파일만 설치하고 구현한 파일은 보존합니다.

```bash
python3 scripts/install_official.py 2
python3 scripts/install_official.py 3
python3 scripts/check_starter.py
```

직접 다운로드한 파일도 사용할 수 있습니다:

```bash
python3 scripts/install_official.py 2 --archive /path/to/assignment2.tar.gz
python3 scripts/install_official.py 3 --archive /path/to/assignment3.tar.gz
```

3번 `src/adapters.py`의 Sandbox·trace logger 인자 형식을 설치된 공식 코드와 비교하세요.
현재 테스트는 공개 문서로 구성한 계약을 검사합니다. 공식 starter 호환성을 검증했다고
볼 수 없으며, 맞지 않는 logger 형식은 조용히 무시하지 않고 오류를 냅니다.

## 실제 실행에 필요한 것

- 1번: Claude Code CLI와 계정 로그인.
- 2·3번: 수업용 `CS2680_API_KEY`, Docker, 공식 starter와 평가 이미지.
- 4·5번: NVIDIA GPU, NVIDIA Container Toolkit, Docker, 모델 다운로드 공간.
- 2번의 실제 과거 프로젝트/오픈소스 이슈 기반 `mytest` 4개와 전후 모델 실행 근거.
- 각 과제의 실제 세션 아카이브, 본인이 작성한 보고서와 영상.

비밀 키는 환경변수에만 넣으세요. 저장소에는 포함하지 않습니다.
수업은 비공개 저장소 제출을 요구합니다. 이 저장소의 공개/비공개 설정은 변경하지 않았습니다.
공식 데이터·평가 인프라와 실행 로그는 기본 gitignore 대상입니다.

## 구조와 검증

공통 런타임의 원본은 `assignment2/src/mads/`입니다. 3번은 `src/`만 제출하므로 같은
코드를 `assignment3/starter_code/src/mads/`에 복사합니다. 수정 후
`python3 scripts/sync_runtime.py`를 실행하고 CI에서 일치 여부를 확인합니다.

```bash
# 루트: 과제 2–5 테스트
python3 -m unittest discover -s tests -v
# 과제 1
cd assignment1
python3 -m unittest discover -s tests -v
node --test tests/model.test.js
```

검증 내역과 한계는 [VALIDATION.md](VALIDATION.md)에 기록했습니다.
이 구현은 OpenAI Codex로 작성했습니다. 학생 개인의 관찰이나 실제 LLM/GPU 결과를
만들어 넣지 않았으며, AI 작성이 금지된 2·3번 제출용 보고서도 생성하지 않았습니다.

## 출처

- https://cs2680.com/assignments/assignment1
- https://cs2680.com/assignments/assignment2
- https://cs2680.com/assignments/assignment3
- https://cs2680.com/assignments/
- https://cs2680.com/to_release
- https://docs.vllm.ai/en/latest/features/tool_calling/
- https://huggingface.co/Qwen/Qwen2.5-7B-Instruct
