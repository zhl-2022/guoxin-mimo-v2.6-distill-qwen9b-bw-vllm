"""Bridge the publisher's unmodified BashOnlyAgent to Harbor's task containers."""
from pathlib import Path
from types import SimpleNamespace
import asyncio
import datetime as dt
import hashlib
import json
import os
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'external/mimoagent016-pinned/src'
sys.path.insert(0,str(SOURCE))
os.environ.setdefault('MIMOAGENT_GLOBAL_CONFIG_DIR',str(ROOT/'evidence/session016/mimoagent-config'))

from harbor.agents.base import BaseAgent
from harbor.agents.capabilities import AgentCapabilities
from harbor.agents.agent_auth_resolution import ModelConnectionSpec, ProviderAccess
from harbor.agents.options import AgentOptions
from harbor.models.model_api_format import ModelApiFormat
from mimoagent.agents.bashonly.bashonly_agent import BashOnlyAgent
from mimoagent.environments import TransportError
from mimoagent.models.openai_chat import OpenAIChatModel

UPSTREAM = 'c3df8469f250b15e7906487a6d52be4c1827a509'
ENDPOINT = 'http://127.0.0.1:19019/v1'


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


class HarborEnvironment:
    def __init__(self,environment,loop,cwd,cancelled,logs):
        self.environment,self.loop,self.cwd = environment,loop,cwd
        self.cancelled,self.logs = cancelled,logs
        self.config = SimpleNamespace(cwd=cwd,timeout=300)
        self.lock = threading.Lock()

    def get_template_vars(self):
        return {'cwd':self.cwd}

    def execute(self,command,cwd='',timeout=None):
        if self.cancelled.is_set():raise TransportError('Harbor trial cancelled')
        seconds = min(300,max(1,int(timeout or 60)))
        tick = time.monotonic()
        future = asyncio.run_coroutine_threadsafe(
            self.environment.exec(command=command,cwd=cwd or self.cwd,timeout_sec=seconds),self.loop)
        try:
            result = future.result(timeout=seconds+30)
            value = {'output':(result.stdout or '')+(result.stderr or ''),'returncode':result.return_code,'reason':'ok'}
        except TimeoutError:
            future.cancel()
            value = {'output':'Harbor command exceeded its deadline','returncode':124,'reason':'client_timeout'}
        except Exception as exc:
            if self.cancelled.is_set():raise TransportError('Harbor trial cancelled') from exc
            raise TransportError(str(exc)) from exc
        with self.lock, (self.logs/'commands.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps({'UTC':now(),'command':command,'cwd':cwd or self.cwd,'timeout':seconds,
                                     'wall_seconds':time.monotonic()-tick,**value},ensure_ascii=False)+'\n')
        return value


class LoggedModel(OpenAIChatModel):
    def __init__(self,logs,context,cancelled,**kwargs):
        super().__init__(**kwargs)
        self.logs,self.context,self.cancelled = logs,context,cancelled

    def query(self,messages,**kwargs):
        if self.cancelled.is_set():raise RuntimeError('Harbor trial cancelled')
        request = {'model':self.config.model_name,'messages':messages,
                   **{k:v for k,v in self.config.model_kwargs.items() if k not in ['base_url','api_key','timeout','max_retries']},
                   **kwargs}
        tick = time.monotonic()
        row = {'UTC':now(),'request':request,
               'semantic_request_sha256':hashlib.sha256(json.dumps(request,sort_keys=True,ensure_ascii=False).encode()).hexdigest()}
        try:
            response = super().query(messages,**kwargs)
            row['response'] = response
            return response
        except BaseException as exc:
            row['error'] = repr(exc)
            raise
        finally:
            stats = self.token_stats
            self.context.n_input_tokens = stats.input_tokens + stats.cache_read_tokens + stats.cache_creation_tokens
            self.context.n_output_tokens = stats.output_tokens
            self.context.n_cache_tokens = stats.cache_read_tokens
            row['wall_seconds'] = time.monotonic()-tick
            with (self.logs/'model-calls.jsonl').open('a',encoding='utf-8') as stream:
                stream.write(json.dumps(row,ensure_ascii=False)+'\n')


class MiMoBashHarborAgent(BaseAgent):
    capabilities = AgentCapabilities(base_url=True)
    options_model = AgentOptions
    MODEL_CONNECTION = ModelConnectionSpec(
        base_url_destination_names={'default':None},
        agent_provider_access=ProviderAccess(api_key_candidate_names=['OPENAI_API_KEY']),
        supported_api_formats=[ModelApiFormat.OPENAI_CHAT_COMPLETIONS])

    @staticmethod
    def name():return 'mimoagent-bashonly-016'

    def version(self):return UPSTREAM

    async def setup(self,environment):
        # The selected publisher profile uses bash only; no software is installed in the task.
        result = await environment.exec('command -v bash',timeout_sec=15)
        assert result.return_code == 0

    async def run(self,instruction,environment,context):
        assert self._base_url == ENDPOINT,'Only the explicitly configured SCNet loopback endpoint is allowed'
        cwd_result = await environment.exec('pwd',timeout_sec=15)
        assert cwd_result.return_code == 0
        cancelled = threading.Event()
        adapter = HarborEnvironment(environment,asyncio.get_running_loop(),cwd_result.stdout.strip(),cancelled,self.logs_dir)
        model = LoggedModel(logs=self.logs_dir,context=context,cancelled=cancelled,
            model_name='mimo-v2.6-distill-qwen-9b',
            model_kwargs={'base_url':ENDPOINT,'api_key':'local-scnet-no-external-api','timeout':360,
                          'max_tokens':32768,'temperature':0.6,'top_p':0.95,
                          'extra_body':{'top_k':20,'chat_template_kwargs':{'enable_thinking':True}}})
        agent = BashOnlyAgent(model,adapter,msg_path=self.logs_dir/'messages.txt')
        record = {'started_utc':now(),'publisher_agent_commit':UPSTREAM,
                  'publisher_agent_profile':'BashOnlyAgent defaults,500 steps,bash timeout60,max300',
                  'model_revision':'2367e865d009c13ac81713a2878291d33ab28177',
                  'adapter_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'upstream_manifest_sha256':hashlib.sha256((ROOT/'evidence/session016/mimoagent-source-manifest.json').read_bytes()).hexdigest(),
                  'verifier_visible_to_model':False,'publisher_exact_leaderboard_harness_config_found':False,
                  'endpoint':ENDPOINT,'submitted':False}
        (self.logs_dir/'native-run-start.json').write_text(json.dumps(record,indent=2))
        try:
            status,message = await asyncio.to_thread(agent.run,instruction)
            record.update(exit_status=status,final_message=message)
        except BaseException as exc:
            record['error'] = repr(exc)
            raise
        finally:
            cancelled.set()
            model.client.close()
            record.update(ended_utc=now(),model_calls=model.n_calls,
                          tool_calls=sum(len(m.get('tool_calls',[])) for m in agent.messages if m['role']=='assistant'))
            context.metadata = record
            (self.logs_dir/'native-run-final.json').write_text(json.dumps(record,indent=2))
            (self.logs_dir/'native-messages.json').write_text(json.dumps(agent.messages,indent=2,ensure_ascii=False))
