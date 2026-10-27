"""Start a private loopback MiMo service for the complete Terminal-Bench run."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import shutil
import socket
import subprocess
import uuid

BASE = Path('/root/private_data/guoxin-hackathon-20261023-session004')
OUT = Path('/root/private_data/guoxin-session016/mimo-agent004')
SLUG = 'mimo-v2.6-distill-qwen9b-bw-vllm'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(8 * 1024**2),b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    prior = json.loads(Path('/root/private_data/guoxin-session014/auk-batch-one-full015/run-final.json').read_text())
    assert prior['complete'] and prior['service_stopped']
    for port in (30000,30109,30119,30129,30139):
        with socket.socket() as sock:
            assert sock.connect_ex(('127.0.0.1',port)) != 0, ('Existing service',port)
    process = Path('/proc/3175/cmdline')
    assert not process.exists() or b'auk_full1088_request015.py' not in process.read_bytes()
    OUT.mkdir(parents=True,exist_ok=False)
    task = OUT / 'project/tasks' / SLUG
    shutil.copytree(BASE / 'tasks' / SLUG,task,ignore=shutil.ignore_patterns('runtime','__pycache__'))
    driver = OUT / 'project/scripts/recon2reason_runtime.py'
    driver.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(BASE / 'scripts/recon2reason_runtime.py',driver)
    shutil.copyfile(Path(__file__),OUT / 'executed-controller.py')
    model = Path('/root/private_data/guoxin-candidates/models/mimo9b')
    lock = json.loads((task / 'model-lock.json').read_text())
    assert lock['revision'] == '2367e865d009c13ac81713a2878291d33ab28177'
    verified = []
    for item in lock['files']:
        path = model / item['path']
        assert path.resolve().is_relative_to(model.resolve()) and path.is_file() and not path.is_symlink()
        assert path.stat().st_size == item['size']
        if 'sha256' in item:
            actual = sha(path)
            assert actual == item['sha256'],item['path']
        else:
            blob = path.read_bytes()
            actual = hashlib.sha1(b'blob '+str(len(blob)).encode()+b'\0'+blob).hexdigest()
            assert actual == item['git_blob_sha1'],item['path']
        verified.append(dict(item,verified=True))
    env = os.environ.copy()
    env.update(MODEL_ID=lock['model_id'],MODEL_PATH=str(model),SERVED_NAME='mimo-v2.6-distill-qwen-9b',
               FRAMEWORK='vllm',PRECISION='bf16',PORT='30109',TP='1',MAX_LEN='204800',MEM_FRAC='0.80',
               LOAD_TIMEOUT='1200',MAX_RUNTIME_SECONDS='43200',STOP_GRACE_SECONDS='30',
               HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
               EXTRA_ARGS_JSON=json.dumps(['--enforce-eager','--max-num-seqs','4','--max-num-batched-tokens','2048',
                                          '--limit-mm-per-prompt','{"image":0,"video":0}',
                                          '--reasoning-parser','qwen3','--enable-auto-tool-choice',
                                          '--tool-call-parser','qwen3_coder']))
    env['LD_LIBRARY_PATH'] = ':'.join(['/opt/ucx/lib','/opt/dtk/dcc/gcvm/lib','/opt/dtk/hip/lib',
                                      '/opt/dtk/llvm/lib','/opt/dtk/lib','/opt/dtk/lib64','/opt/hyhal/lib',
                                      '/opt/hyhal/lib64','/opt/dtk/dushmem/lib','/opt/dtk/opencl/lib',
                                      '/opt/mpi/lib','/opt/hwloc/lib',env.get('LD_LIBRARY_PATH','')])
    env.update(ROCM_PATH='/opt/dtk',HIP_PATH='/opt/dtk/hip')
    env['PATH'] = '/opt/ucx/bin:/opt/dtk/bin:/opt/dtk/llvm/bin:/opt/dtk/hip/bin:/opt/hyhal/bin:' + env.get('PATH','/usr/bin:/bin')
    run_id = uuid.uuid4().hex
    record = {'started_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'run_id':run_id,
              'checkpoint_revision':lock['revision'],'verified_files':verified,'source_sha256':sha(Path(__file__)),
              'runtime_sha256':sha(driver),'model_max_len':204800,'max_num_seqs':4,'owned_service_watchdog_seconds':43200,
              'reasoning_parser':'native qwen3; checked against this checkpoint think delimiters',
              'submitted':False,'official_accuracy_verified':False,'instance_shutdown_requested':False}
    (OUT / 'launch-start.json').write_text(json.dumps(record,indent=2))
    with (OUT / 'launch.log').open('xb') as log:
        result = subprocess.run(['python3',str(driver),'launch','--task-dir',str(task),'--run-id',run_id],
                                env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1260)
    record['launch_exit_code'] = result.returncode
    record['ready'] = result.returncode == 0
    record['launch_finished_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    (OUT / 'launch-final.json').write_text(json.dumps(record,indent=2))
    print(json.dumps({k:v for k,v in record.items() if k != 'verified_files'}),flush=True)


if __name__ == '__main__':
    main()
