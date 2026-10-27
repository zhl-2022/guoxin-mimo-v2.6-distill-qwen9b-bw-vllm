"""Independently classify all89 final scores; legitimate timeouts remain failures.

The running018 producer counts every exception in its errors total, including
Harbor AgentTimeoutError. A verified zero reward at the normal task deadline is
a scored failure, not a transport failure and never a reason to resample.
"""
from pathlib import Path
import argparse
import datetime as dt
import hashlib
import json
import math


ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / 'evidence/session016'
JOBS = STATE / 'harbor-mimo'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_path(unix_path):
    prefix = '/mnt/e/hg20261019/'
    assert unix_path.startswith(prefix), 'Unexpected source workspace'
    target = ROOT / unix_path[len(prefix):]
    assert target.resolve().is_relative_to(JOBS.resolve()) and not target.is_symlink()
    assert target.name == 'result.json'
    return target


def trial_kind(value):
    exception = (value.get('exception_info') or {}).get('exception_type')
    rewards = (value.get('verifier_result') or {}).get('rewards') or {}
    reward = rewards.get('reward')
    has_reward = type(reward) in (int, float) and math.isfinite(reward) and reward in (0, 1)
    if exception is None and has_reward:
        return 'scored', int(reward)
    if exception == 'AgentTimeoutError' and has_reward and reward == 0:
        return 'scored_normal_task_timeout', 0
    return 'unresolved', None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    selection = STATE / 'mimo-full89-selection018.json'
    assert selection.is_file(), 'The complete018 selection does not exist; never extrapolate partial trials'
    config = json.loads((STATE / 'mimo-native-full017.json').read_text())
    names = {Path(t['path']).name for t in config['tasks']}
    assert len(names) == 89 and config['retry']['max_retries'] == 0
    histories = json.loads(selection.read_text())
    assert set(histories) == names
    rows = []
    unresolved = []
    successes = 0
    for name in sorted(names):
        history = histories[name]
        assert history
        for i, item in enumerate(history):
            path = local_path(item['path'])
            assert sha(path) == item['sha256'], ('Result mutated', name, i)
            value = json.loads(path.read_text())
            assert Path(value['config']['task']['path']).name == name
            assert value.get('finished_at'), ('Unfinished trial', name, i)
            exception = (value.get('exception_info') or {}).get('exception_type')
            assert exception == item['exception']
            assert ((value.get('verifier_result') or {}).get('rewards')) == item['rewards']
            kind, reward = trial_kind(value)
            if i < len(history) - 1:
                assert kind == 'unresolved', ('A normal scored attempt was retried', name, i)
        row = {'task': name, 'classification': kind, 'reward': reward,
               'selected_result_path': history[-1]['path'], 'selected_result_sha256': history[-1]['sha256'],
               'attempts_preserved': len(history), 'exception': exception}
        rows.append(row)
        if reward == 1:
            successes += 1
        if kind == 'unresolved':
            unresolved.append(name)
    complete = not unresolved
    producer = json.loads((STATE / 'mimo-native-controller-progress018.json').read_text())
    score = 100 * successes / 89
    result = {'UTC': dt.datetime.now(dt.timezone.utc).isoformat(), 'auditor_sha256': sha(Path(__file__)),
              'selection_sha256': sha(selection), 'full_task_count': 89, 'denominator': 89,
              'complete_scored_evaluation': complete, 'successes': successes, 'score_percent': score,
              'publisher_SFT_baseline_percent': 37.1, 'absolute_threshold_percent': 35.1,
              'minimum_successes': 32, 'numeric_pass': complete and successes >= 32,
              'normal_deadline_failures': sum(r['classification'] == 'scored_normal_task_timeout' for r in rows),
              'unresolved_infrastructure_or_unknown_failures': unresolved,
              'normal_reward_zero_retried': False, 'producer_state': producer.get('state'),
              'producer_raw_exception_count': producer.get('errors'),
              'classification_note': 'Retain verified AgentTimeout reward0 in all89. It cannot be retried or excluded to increase score.',
              'publisher_exact_leaderboard_harness_config_found': False,
              'technical_delivery_complete': False, 'official_acceptance': False, 'submitted': False, 'tasks': rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'tasks'}, ensure_ascii=False), flush=True)
    return 0 if complete else 1


if __name__ == '__main__':
    raise SystemExit(main())
