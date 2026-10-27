"""Check publisher streaming tool assembly against the real loopback model."""
from pathlib import Path
import json
from mimo_harbor_native018 import OpenAIChatModel,ENDPOINT

ROOT=Path(__file__).resolve().parents[2]
model=OpenAIChatModel(model_name='mimo-v2.6-distill-qwen-9b',model_kwargs={
    'base_url':ENDPOINT,'api_key':'local-scnet-no-external-api','timeout':360,
    'stream':True,'max_tokens':512,'temperature':0,'extra_body':{'chat_template_kwargs':{'enable_thinking':True}}})
messages=[{'role':'user','content':'Call the bash tool to run exactly: printf stream_tool_018. Do not add explanations.'}]
tools=[{'type':'function','function':{'name':'bash','description':'Execute a shell command',
       'parameters':{'type':'object','properties':{'command':{'type':'string'}},'required':['command']}}}]
try:
    response=model.query(messages,tools=tools,tool_choice='auto')
    calls=response.get('tool_calls',[])
    assert calls and calls[0]['function']['name']=='bash',response
    assert json.loads(calls[0]['function']['arguments'])['command']=='printf stream_tool_018',response
    record={'actual_model_endpoint':ENDPOINT,'publisher_streaming_assembler':True,
            'full_generation_budget_unchanged_for_benchmark':True,'smoke_max_tokens':512,
            'tool_call_exactly_reassembled':True,'response':response,'formal_accuracy_sample':False}
    target=ROOT/'evidence/session017/mimo-streaming-tool-smoke018.json'
    with target.open('x') as stream:stream.write(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record))
finally:model.client.close()
