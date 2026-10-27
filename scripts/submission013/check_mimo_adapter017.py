"""Exercise the real Harbor timeout collector through the publisher bash tool."""
from pathlib import Path
import asyncio
import json
import tempfile
import threading
from mimo_harbor_native017 import HarborEnvironment,TransportError
from harbor.environments.docker.docker import DockerEnvironment
from mimoagent.tools.bashonly.bash_only import BashOnlyTool


class LocalCollector:
    async def exec(self,command,cwd,timeout_sec):
        if command=='transport_failure':raise RuntimeError('Docker transport lost')
        process=await asyncio.create_subprocess_exec('bash','-c',command,
                    stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        return await DockerEnvironment._collect_buffered_output(process,timeout_sec=timeout_sec)


async def main():
    with tempfile.TemporaryDirectory() as temporary:
        adapter=HarborEnvironment(LocalCollector(),asyncio.get_running_loop(),'/tmp',threading.Event(),Path(temporary))
        timeout=await asyncio.to_thread(adapter.execute,'sleep 2',timeout=1)
        assert timeout['returncode']==124 and timeout['reason']=='client_timeout',timeout
        recovered=await asyncio.to_thread(adapter.execute,'printf recovered',timeout=2)
        assert recovered['returncode']==0 and recovered['output']=='recovered',recovered
        try:await asyncio.to_thread(adapter.execute,'transport_failure',timeout=2)
        except TransportError:pass
        else:raise AssertionError('Unexpected infrastructure failure was swallowed')
        print(json.dumps({'real_Harbor_timeout_collector':True,'timeout_returncode':124,
                          'publisher_reason':'client_timeout','next_command_succeeded':True,
                          'transport_failure_still_raises':True,'GPU_requests':0}))


if __name__=='__main__':asyncio.run(main())
