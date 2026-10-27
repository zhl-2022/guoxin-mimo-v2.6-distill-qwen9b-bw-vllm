"""Run every frozen task; retain infrastructure retries in separate job folders."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import signal
import subprocess
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'evidence/session016'
STATE=OUT/'mimo-native-controller-progress017.json'
CONFIG=OUT/'mimo-native-full017.json'
INFRA={'RuntimeError','EnvironmentStartTimeoutError','EnvironmentBuildError'}


def now():return dt.datetime.now(dt.timezone.utc).isoformat()


def save(record):
    temporary=STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps(record,indent=2)+'\n');temporary.replace(STATE)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def health(timeout=1200):
    deadline=time.monotonic()+timeout
    while True:
        try:
            with urllib.request.urlopen('http://127.0.0.1:19019/health',timeout=5) as r:
                if r.status==200:return
        except Exception:pass
        assert time.monotonic()<deadline,'MiMo local tunnel/service not healthy'
        time.sleep(5)


def run(config,label,record):
    health()
    path=OUT/(label+'.json')
    if path!=CONFIG:
        with path.open('x') as stream:stream.write(json.dumps(config,indent=2)+'\n')
    log=OUT/(label+'-console.log')
    with log.open('xb') as stream:
        child=subprocess.Popen([str(ROOT/'external/harbor-env015/bin/harbor'),'run','--config',str(path)],
                  stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        record.update(state='running',active_job=config['job_name'],harbor_pid=child.pid,active_started_utc=now())
        save(record)
        deadline=time.monotonic()+36000
        try:
            while child.poll() is None:
                assert time.monotonic()<deadline,'Owned Harbor job exceeded 10 hours'
                time.sleep(10)
            return child.returncode
        except BaseException:
            os.killpg(child.pid,signal.SIGINT)
            try:child.wait(timeout=45)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGTERM);child.wait(timeout=30)
            raise


def results(config):
    job=Path(config['jobs_dir'])/config['job_name']
    rows={}
    for path in job.glob('*/result.json'):
        row=json.loads(path.read_text())
        name=Path(row['config']['task']['path']).name
        assert name not in rows,'Multiple model attempts were not authorized for scoring'
        rows[name]={'result':row,'path':str(path),'sha256':sha(path)}
    return rows


def main():
    os.environ.update(OPENAI_API_KEY='local-scnet-no-external-api',LITELLM_LOCAL_MODEL_COST_MAP='True',
        PYTHONPATH=str(ROOT/'scripts/submission013'),MIMOAGENT_GLOBAL_CONFIG_DIR=str(OUT/'mimoagent-config'))
    manifest=json.loads((OUT/'mimoagent-source-manifest.json').read_text())
    for row in manifest['files']:
        raw=(ROOT/'external/mimoagent016-pinned'/row['path']).read_bytes()
        assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==row['sha']
    config=json.loads(CONFIG.read_text())
    names=[Path(t['path']).name for t in config['tasks']]
    assert len(names)==len(set(names))==89 and config['retry']['max_retries']==0
    assert not (Path(config['jobs_dir'])/config['job_name']).exists()
    record={'started_utc':now(),'state':'waiting_service','tasks':89,'all_tasks_in_denominator':True,
            'agent_commit':manifest['commit'],'adapter_sha256':sha(ROOT/'scripts/submission013/mimo_harbor_native017.py'),
            'controller_sha256':sha(Path(__file__)),'config_sha256':sha(CONFIG),
            'publisher_exact_leaderboard_harness_config_found':False,
            'prior_full016_invalid_for_accuracy':'Tunnel disconnect and tool-timeout adapter error; all raw files retained',
            'infrastructure_retries_preserve_originals':True,'jobs':[],
            'submitted':False,'instance_shutdown_requested':False}
    save(record)
    chosen={};history={name:[] for name in names}
    for attempt in range(3):
        if attempt:
            pending=[name for name,value in chosen.items()
                     if (value['result'].get('exception_info') or {}).get('exception_type') in INFRA]
            if not pending:break
            config=dict(config,job_name=f'mimo-native-infra-retry017-{attempt}',
                        tasks=[t for t in json.loads(CONFIG.read_text())['tasks'] if Path(t['path']).name in pending])
        label='mimo-native-full017' if attempt==0 else config['job_name']
        exit_code=run(config,label,record)
        current=results(config)
        expected={Path(t['path']).name for t in config['tasks']}
        assert set(current)==expected,('Missing task results',expected-set(current))
        for name,value in current.items():history[name].append(value);chosen[name]=value
        record['jobs'].append({'name':config['job_name'],'tasks':len(expected),'exit_code':exit_code})
        record['infrastructure_errors_remaining']=sum(v['result'].get('exception_info') is not None for v in chosen.values())
        save(record)
    assert set(chosen)==set(names)
    successes=sum(float(((v['result'].get('verifier_result') or {}).get('rewards') or {}).get('reward',0))>=1
                  for v in chosen.values())
    errors=sum(v['result'].get('exception_info') is not None for v in chosen.values())
    complete=len(chosen)==89 and errors==0
    selection={name:[{'path':x['path'],'sha256':x['sha256'],
                      'exception_type':(x['result'].get('exception_info') or {}).get('exception_type'),
                      'rewards':(x['result'].get('verifier_result') or {}).get('rewards')}
                      for x in history[name]] for name in names}
    with (OUT/'mimo-native-full017-selection.json').open('x') as stream:
        stream.write(json.dumps(selection,indent=2)+'\n')
    record.update(state='complete' if complete else 'complete_with_errors',ended_utc=now(),
        successes=successes,score_percent=100*successes/89,infrastructure_errors_remaining=errors,
        publisher_baseline_percent=37.1,threshold_percent=35.1,numeric_pass=complete and successes>=32)
    save(record);print(json.dumps(record),flush=True)


if __name__=='__main__':
    try:main()
    except BaseException as exc:
        record=json.loads(STATE.read_text()) if STATE.exists() else {}
        record.update(state='failed',error=repr(exc),ended_utc=now(),submitted=False)
        save(record);raise
