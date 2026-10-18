# Assignment 4 — Mads-Serve (공개 개요 기반 선행 구현)

**2026-10-18 현재 상세 명세 미공개.** 공식 공개일은 10월 21일입니다.
7–8B 오픈웨이트 모델을 직접 서빙한다는 개요에 맞춰 Qwen2.5-7B-Instruct를 선택했습니다.
상용 API fallback과 더 큰 모델로의 자동 전환은 없습니다.

## 시작

Linux, Docker, NVIDIA GPU 및 NVIDIA Container Toolkit이 필요합니다.
GPU VRAM 요구량은 context·동시 요청·dtype에 따라 달라집니다. OOM이면 동시성 및
max-model-len을 줄이거나 AWQ profile을 별도로 실험하세요. 이 환경에서는 GPU 실행을 하지 않았습니다.

```bash
# 저장소 루트
python3 assignment4/serve.py --dry-run
python3 assignment4/serve.py
```

별도 터미널:

```bash
python3 assignment4/check_endpoint.py
python3 assignment4/run_agent.py \
  -p 'battery.py에서 음수 SOC가 0으로 제한되지 않는 버그를 고쳐줘' \
  assignment5/workloads/ess/soc_clamp
```

위 명령은 해당 예제 파일을 실제로 수정합니다. 비교 실험은 5번 runner로 실행하면
임시 복사본마다 독립적으로 수정하고 평가할 수 있습니다.
`--allow-shell`은 disposable 환경에서만 사용하세요. 파일 수정 도구만으로도 작은 예제는 실행 가능합니다.
remote GPU에는 SSH 터널로 localhost:8000을 연결하세요. 상용 endpoint 실수 사용을 줄이기 위해
`run_agent.py`는 loopback 주소만 허용합니다.

## 선택과 관측

- vLLM `v0.11.0` 이미지로 버전을 고정했습니다. 최신 버전이라는 뜻은 아닙니다.
- 모델의 Hermes-style tool template에 맞춰 `--enable-auto-tool-choice --tool-call-parser hermes` 사용.
- 16K context, 기본 8개 sequence, baseline prefix cache 비활성.
- `check_endpoint.py`는 실제 structured tool_calls 반환 여부만 확인하며 도구를 실행하지 않습니다.
- `configs/agent.json`은 작은 모델을 위해 tool output과 context를 줄이고 읽기 병렬 호출을 끕니다.

모델 출력 품질·정확도 저하·복구 정도는 같은 workload의 실제 평가로 판단해야 합니다.
현재 측정값은 없으며, 5번 비교 runner를 통해 frontier 기준 결과와 자체 서빙 결과를 비교할 수 있습니다.
현재 serving config는 입력한 설정을 기록할 뿐 실행 서버의 실제 설정을 자동 검증하지 않습니다.

출처: https://cs2680.com/assignments/
https://cs2680.com/to_release
https://docs.vllm.ai/en/latest/features/tool_calling/
https://huggingface.co/Qwen/Qwen2.5-7B-Instruct
