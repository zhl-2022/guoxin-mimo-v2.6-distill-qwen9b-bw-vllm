#!/usr/bin/env python3
"""Transparent canonical task entry; does not synthesize evaluation results."""
import os
from pathlib import Path
import sys

entry = Path(__file__).resolve().parent / 'tasks/mimo-v2.6-distill-qwen9b-bw-vllm/verify.sh'
try:
    os.execvp('bash', ['bash', str(entry), *sys.argv[1:]])
except OSError as exc:
    print(f'Cannot execute canonical entry: {exc}', file=sys.stderr)
    raise SystemExit(2)
