"""Launch a pinned vLLM container. Preliminary A4 implementation: full spec unreleased."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess

BASE = Path(__file__).resolve().parent
ALLOWED_MODELS = {'Qwen/Qwen2.5-7B-Instruct', 'Qwen/Qwen2.5-7B-Instruct-AWQ'}


def command(config):
    if config['model'] not in ALLOWED_MODELS:
        raise ValueError('A4 profile permits only the selected 7B model or its AWQ variant')
    if config.get('tensor_parallel_size', 1) < 1:
        raise ValueError('tensor_parallel_size must be positive')
    cache = Path(os.environ.get('MADS_MODEL_CACHE', str(Path.home() / '.cache/huggingface'))).expanduser().resolve()
    cmd = ['docker', 'run', '--rm', '--gpus', 'all', '--ipc=host',
           '-p', f"127.0.0.1:{config.get('port', 8000)}:8000",
           '-v', f'{cache}:/root/.cache/huggingface',
           config['image'], '--model', config['model'], '--served-model-name', 'mads-7b',
           '--host', '0.0.0.0', '--port', '8000', '--enable-auto-tool-choice',
           '--tool-call-parser', 'hermes', '--max-model-len', str(config['max_model_len']),
           '--max-num-seqs', str(config['max_num_seqs']), '--max-num-batched-tokens', str(config['max_num_batched_tokens']),
           '--gpu-memory-utilization', str(config.get('gpu_memory_utilization', .9)),
           '--tensor-parallel-size', str(config.get('tensor_parallel_size', 1)),
           '--dtype', config.get('dtype', 'auto')]
    cmd.append('--enable-prefix-caching' if config.get('prefix_caching', False) else '--no-enable-prefix-caching')
    if config.get('quantization'):
        cmd.extend(['--quantization', config['quantization']])
    return cmd


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=BASE / 'configs/baseline.json')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    cmd = command(config)
    print(shlex.join(cmd), flush=True)
    if not args.dry_run:
        subprocess.run(cmd, check=True)
