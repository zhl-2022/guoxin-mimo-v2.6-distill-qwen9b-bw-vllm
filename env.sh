#!/usr/bin/env bash
_TASK_REPOSITORY_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$_TASK_REPOSITORY_ROOT/tasks/mimo-v2.6-distill-qwen9b-bw-vllm/env.sh"
unset _TASK_REPOSITORY_ROOT
