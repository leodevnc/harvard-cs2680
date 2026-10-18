# Assignment 5 — Mads-Stack (공개 개요 기반 선행 구현)

**상세 명세는 2026-11-11 공개 예정**입니다. 현재는 공개 개요에 맞춘 재현 가능한
실험 runner와 serving profile을 구현했습니다. 실제 성능 향상 수치는 아직 없습니다.

## 기준 실험

4번 baseline server를 먼저 실행합니다. 저장소 루트에서:

```bash
python3 assignment5/experiment.py \
  --tasks assignment5/workloads/ess.json \
  --agent-config assignment4/configs/agent.json \
  --serving-config assignment4/configs/baseline.json \
  --hypothesis 'Baseline: 캐시 없이 고정된 ESS 예제의 정확도와 실행 시간을 측정한다.' \
  --concurrency 1 --repeats 3 --output results/baseline
```

모델은 실제 실행되므로 GPU endpoint가 준비되어 있어야 합니다. 각 task는 임시 복사본에서
시작합니다. 원본이 git repo면 committed snapshot을 clone합니다. 미커밋 변경은 포함하지 않습니다.
원본에 symlink나 비밀 파일이 없는 실습 프로젝트를 쓰세요.
기존 output 디렉터리는 덮어쓰지 않습니다.

가설·workload hash·source hash·설정은 모델 호출 전에 저장합니다.
검증용 `protected_files` 변경은 검출하고 복원한 후 테스트를 실행합니다.
모델이 `done`을 호출해도 테스트가 실패하면 solved로 처리하지 않습니다.
이미 baseline에서 통과하는 task도 새로 해결했다고 세지 않습니다.
이 verifier는 로컬 실험용이며 공식 SWE-bench grader를 대체하지 않습니다.

## 최적화 실험

baseline 서버를 종료하고 다음 profile을 실행합니다:

```bash
python3 assignment4/serve.py --config assignment5/configs/prefix_batch.json
```

동일한 task와 반복 수로:

```bash
python3 assignment5/experiment.py \
  --tasks assignment5/workloads/ess.json \
  --agent-config assignment5/configs/optimized_agent.json \
  --serving-config assignment5/configs/prefix_batch.json \
  --hypothesis '동일 접두사 캐시와 읽기 병렬 실행이 성공 task를 유지하면서 wall time과 입력량을 줄인다.' \
  --concurrency 4 --repeats 3 --output results/optimized
python3 assignment5/compare.py results/baseline results/optimized --output results/comparison.json
```

이 예시는 여러 변수를 한꺼번에 변경합니다. 어느 변경이 기여했는지 판단하려면
① prefix cache만 ② 동시성만 ③ context/output cap만 각각 바꾼 실험도 수행하세요.
AWQ는 별도의 `configs/awq.json` profile입니다. 메모리 절감과 정확도 손실을 함께 측정해야 합니다.
speculative decoding은 이 구현에 포함하지 않았습니다.

## 측정

```bash
python3 assignment5/profile_server.py \
  --prompts assignment5/workloads/prompts.json \
  --concurrency 4 --output results/serving-profile.json
```

- TTFT: 실제 content/tool/reasoning delta가 처음 도착한 시간. role-only chunk는 제외.
- TPOT: 첫 내용 도착부터 종료까지 시간 / (completion tokens − 1).
  마지막 usage/framing의 전달 시간이 조금 포함됩니다.
- output throughput: 전체 완료 토큰 / 전체 host wall time.
- 에이전트: API·tool 시간, token 사용, retries, context 정리, 캐시 hit, tool error.
- 비교: 동일 workload·source·반복수만 비교, task별 regression과 성공당 wall time 산출.

GPU utilization/VRAM은 `nvidia-smi`, 서버 큐·KV cache는 vLLM `/metrics`와 함께 확인하세요.
현재 runner가 GPU 하드웨어 telemetry를 자동 수집한다고 주장하지 않습니다.
warmup 제외나 cache flush는 자동 수행하지 않으므로 실험자가 통제하고 기록해야 합니다.
serving config 파일과 실행 서버의 실제 설정이 같은지도 확인하세요.

`workloads/ess.json`은 합성 학습용 예제입니다. 공식 과제2 mytest의 실제 이슈 4개 조건을
충족하는 데이터로 제시하지 않습니다. 일반화 성능 판단에는 실제 문제와 별도 holdout이 필요합니다.
