"""After initial full017, retain valid scores and repair only infra/pending tasks."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import signal
import time
import run_mimo_native_harbor017 as common

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'evidence/session016'
STATE=OUT/'mimo-native-controller-progress018.json'
common.STATE=STATE
PRIOR=OUT/'harbor-mimo/mimo-native-full017'
INFRA=common.INFRA|{'CancelledError'}


def now():return dt.datetime.now(dt.timezone.utc).isoformat()


def process_identity(pid):
    try:
        root=Path('/proc')/str(pid)
        return (root/'stat').read_text().rsplit(')',1)[1].split()[19],(root/'cmdline').read_bytes()
    except (FileNotFoundError,ProcessLookupError):return None,None


def main():
    assert not STATE.exists(),'Repair controller already registered'
    smoke=ROOT/'evidence/session017/mimo-streaming-tool-smoke018.json'
    assert json.loads(smoke.read_text())['tool_call_exactly_reassembled']
    os.environ.update(OPENAI_API_KEY='local-scnet-no-external-api',LITELLM_LOCAL_MODEL_COST_MAP='True',
        PYTHONPATH=str(ROOT/'scripts/submission013'),MIMOAGENT_GLOBAL_CONFIG_DIR=str(OUT/'mimoagent-config'))
    config=json.loads(common.CONFIG.read_text())
    names={Path(t['path']).name for t in config['tasks']};assert len(names)==89
    control=json.loads((OUT/'mimo-native-controller-progress017.json').read_text())
    child=control['harbor_pid']
    parent=int(next(s for s in (Path('/proc')/str(child)/'status').read_text().splitlines() if s.startswith('PPid:')).split()[1])
    token,command=process_identity(parent)
    assert b'/run_mimo_native_harbor017.py' in command
    record={'started_utc':now(),'state':'waiting_initial_full017','controller_pid':os.getpid(),
            'prior_owner_pid':parent,'prior_owner_start_token':token,
            'controller_sha256':common.sha(Path(__file__)),
            'adapter_sha256':common.sha(ROOT/'scripts/submission013/mimo_harbor_native018.py'),
            'stream_tool_smoke_sha256':common.sha(smoke),'tasks':89,'all_tasks_in_denominator':True,
            'model_sampling_budget_changed':False,'wire_change':'Publisher native streaming instead of nonstreaming; 360s between-byte timeout',
            'valid_completed_reward_zero_retained':True,'submitted':False,'instance_shutdown_requested':False,'jobs':[]}
    common.save(record)
    while True:
        try:
            progress=json.loads((PRIOR/'result.json').read_text())
            stats=progress['stats']
            phase_done=stats['n_completed_trials']==89 and stats['n_running_trials']==0
        except (FileNotFoundError,json.JSONDecodeError):phase_done=False
        current,current_command=process_identity(parent)
        if phase_done or current!=token:break
        time.sleep(5)
    if current==token:
        assert b'/run_mimo_native_harbor017.py' in current_command
        # Stop its prospective six-minute-timeout retry loop after first89,
        # while preserving every completed trial and the remote GPU service.
        os.kill(parent,signal.SIGINT)
        record['old_retry_controller_interrupted_after_initial_phase']=True;common.save(record)
        deadline=time.monotonic()+100
        while process_identity(parent)[0]==token:
            assert time.monotonic()<deadline,'Prior owner has not completed cleanup'
            time.sleep(2)
    original=dict(config)
    chosen=common.results(original)
    assert set(chosen)<=names
    history={name:([chosen[name]] if name in chosen else []) for name in names}
    config=dict(config,agents=[dict(a,import_path='mimo_harbor_native018:MiMoBashHarborAgent') for a in config['agents']])
    for attempt in range(3):
        pending=[name for name in names if name not in chosen or
                 (chosen[name]['result'].get('exception_info') or {}).get('exception_type') in INFRA]
        if not pending:break
        cfg=dict(config,job_name=f'mimo-native-repair018-{attempt}',
                 tasks=[t for t in original['tasks'] if Path(t['path']).name in pending])
        assert cfg['retry']['max_retries']==0
        exit_code=common.run(cfg,cfg['job_name'],record)
        current_results=common.results(cfg)
        assert set(current_results)==set(pending)
        for name,value in current_results.items():chosen[name]=value;history[name].append(value)
        record['jobs'].append({'name':cfg['job_name'],'tasks':len(pending),'exit_code':exit_code});common.save(record)
    assert set(chosen)==names
    successes=sum(float(((v['result'].get('verifier_result') or {}).get('rewards') or {}).get('reward',0))>=1
                  for v in chosen.values())
    errors=sum(v['result'].get('exception_info') is not None for v in chosen.values())
    selection={name:[{'path':v['path'],'sha256':v['sha256'],
                       'exception':(v['result'].get('exception_info') or {}).get('exception_type'),
                       'rewards':(v['result'].get('verifier_result') or {}).get('rewards')}
                      for v in history[name]] for name in sorted(names)}
    with (OUT/'mimo-full89-selection018.json').open('x') as stream:stream.write(json.dumps(selection,indent=2)+'\n')
    record.update(state='complete' if errors==0 else 'complete_with_errors',ended_utc=now(),
                  successes=successes,score_percent=100*successes/89,errors=errors,
                  publisher_baseline_percent=37.1,threshold_percent=35.1,numeric_pass=errors==0 and successes>=32)
    common.save(record);print(json.dumps(record),flush=True)


if __name__=='__main__':
    try:main()
    except BaseException as exc:
        record=json.loads(STATE.read_text()) if STATE.exists() else {}
        record.update(state='failed',error=repr(exc),ended_utc=now(),submitted=False)
        common.save(record);raise
