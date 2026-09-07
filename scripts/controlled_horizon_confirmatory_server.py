#!/usr/bin/env python
"""Launch the pinned local server and write a private provenance receipt."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.controlled_horizon_confirmatory import load_protocol
from scripts.controlled_horizon_model_pilot import validate_serving_stack, _package_version
from scripts.controlled_horizon_pilot import _atomic_write_json


def server_command(protocol, port):
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise ValueError('invalid server port')
    inf = protocol['inference']
    stack = inf['serving_stack']
    return ['-m', 'vllm.entrypoints.openai.api_server', '--model', inf['model_repository'],
            '--revision', inf['model_revision'], '--served-model-name', inf['served_model_name'],
            '--tensor-parallel-size', str(stack['tensor_parallel_size']),
            '--max-model-len', str(stack['max_model_len']),
            '--gpu-memory-utilization', str(stack['gpu_memory_utilization']),
            '--host', '127.0.0.1', '--port', str(port)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--authorize-model-inference', action='store_true')
    args = parser.parse_args()
    if not args.authorize_model_inference:
        parser.error('server startup requires --authorize-model-inference')
    if args.receipt.exists():
        parser.error('receipt exists; preserve it and choose a new path')
    p, digest = load_protocol()
    validate_serving_stack(p)
    command = server_command(p, args.port)
    # Replace this process, preserving its PID for local liveness checks.
    receipt = dict(protocol_digest=digest, command=command, port=args.port,
                   endpoint_sha256=hashlib.sha256(f'http://localhost:{args.port}/v1'.encode()).hexdigest(),
                   runtime_versions={k: _package_version(k) for k in ('vllm', 'transformers')},
                   launch_id=uuid.uuid4().hex, pid=os.getpid(),
                   created_at_utc=dt.datetime.now(dt.timezone.utc).isoformat())
    if sys.platform == 'win32':
        parser.error('pinned serving launcher requires the Linux serving environment')
    _atomic_write_json(args.receipt, receipt)
    os.execv(sys.executable, [sys.executable] + command)


if __name__ == '__main__':
    main()
