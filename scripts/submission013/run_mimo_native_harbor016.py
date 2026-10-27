"""Check native tools on one separate task, then run all89 frozen benchmark tasks."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import signal
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'evidence/session016'
HARBOR = ROOT/'external/harbor-env015/bin/harbor'


def now():return dt.datetime.now(dt.timezone.utc).isoformat()


def save(value):
    temporary = OUT/'mimo-native-controller-progress.tmp'
    temporary.write_text(json.dumps(value,indent=2)+'\n')
    temporary.replace(OUT/'mimo-native-controller-progress.json')


def run(config,log,timeout):
    with log.open('xb') as stream:
        child = subprocess.Popen([str(HARBOR),'run','--config',str(config)],stdin=subprocess.DEVNULL,
                                 stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        try:return child.wait(timeout=timeout)
        except BaseException:
            os.killpg(child.pid,signal.SIGINT)
            try:child.wait(timeout=45)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGTERM)
                child.wait(timeout=30)
            raise


def main():
    envvars = {'OPENAI_API_KEY':'local-scnet-no-external-api','LITELLM_LOCAL_MODEL_COST_MAP':'True',
               'PYTHONPATH':str(ROOT/'scripts/submission013'),
               'MIMOAGENT_GLOBAL_CONFIG_DIR':str(OUT/'mimoagent-config')}
    os.environ.update(envvars)
    manifest = json.loads((OUT/'mimoagent-source-manifest.json').read_text())
    for row in manifest['files']:
        raw = (ROOT/'external/mimoagent016-pinned'/row['path']).read_bytes()
        assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest() == row['sha']
    with urllib.request.urlopen('http://127.0.0.1:19019/health',timeout=10) as response:assert response.status == 200
    record = {'started_utc':now(),'state':'native_smoke_running','smoke_counted_as_accuracy':False,
              'official_agent_commit':manifest['commit'],'source_files_verified':len(manifest['files']),
              'submitted':False,'instance_shutdown_requested':False}
    save(record)
    record['smoke_exit_code'] = run(OUT/'mimo-native-smoke.json',OUT/'mimo-native-smoke-console.log',1800)
    job = OUT/'harbor-mimo/mimo-native-smoke016'
    summary = json.loads((job/'result.json').read_text())
    runs = list(job.glob('*/agent/native-run-final.json'))
    assert len(runs) == 1
    native = json.loads(runs[0].read_text())
    assert record['smoke_exit_code'] == 0 and summary['stats']['n_errored_trials'] == 0
    assert native.get('tool_calls',0) > 0 and 'error' not in native
    assert len(list(job.glob('*/verifier/reward.*'))) > 0
    record.update(state='full89_running',full_started_utc=now(),smoke_tool_calls=native['tool_calls'])
    save(record)
    print(json.dumps(record),flush=True)
    record['full_exit_code'] = run(OUT/'mimo-native-full.json',OUT/'mimo-native-full-console.log',18000)
    job = OUT/'harbor-mimo/mimo-native-full016'
    summary = json.loads((job/'result.json').read_text())
    trials = [json.loads(p.read_text()) for p in job.glob('*/result.json')]
    successes = sum(float((r.get('verifier_result') or {}).get('rewards',{}).get('reward',0)) >= 1 for r in trials)
    complete = record['full_exit_code'] == 0 and len(trials) == 89 and summary['stats']['n_errored_trials'] == 0
    record.update(state='complete' if complete else 'incomplete_or_errors',ended_utc=now(),
                  trials_found=len(trials),successes=successes,score_percent=100*successes/89,
                  publisher_baseline_percent=37.1,threshold_percent=35.1,
                  numeric_pass=complete and successes>=32,publisher_exact_harness_config_found=False)
    save(record)
    print(json.dumps(record),flush=True)


if __name__ == '__main__':
    try:main()
    except BaseException as exc:
        path=OUT/'mimo-native-controller-progress.json'
        record=json.loads(path.read_text()) if path.exists() else {'started_utc':now()}
        record.update(state='failed',error=repr(exc),ended_utc=now(),submitted=False)
        save(record)
        raise
