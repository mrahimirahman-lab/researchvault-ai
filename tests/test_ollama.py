"""Ollama protocol tests use controlled responses; no real model download."""
import json
import os
import subprocess
import sys
import pytest
import requests
from core.database import Database
from core.models import Synthesis
from services.ai import AI
from services.ollama import Ollama

SYNTHESIS = dict(draft='Fixture synthesis [e1].', similarities=[], differences=[], limitations=['Synthetic fixture only'], cited_evidence_ids=['e1'])

def test_native_chat_schema_and_no_key(monkeypatch,tmp_path):
    import services.ai as module
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    monkeypatch.setattr(module,'PROVIDER','ollama')
    monkeypatch.setattr(module,'ai_enabled',lambda:True)
    seen=[]
    def request(self,path,payload=None):
        seen.append((path,payload))
        return {'done':True,'done_reason':'stop','message':{'content':json.dumps(SYNTHESIS)}}
    monkeypatch.setattr(Ollama,'request',request)
    result=AI(Database(tmp_path)).call(Synthesis,{'question':'test'})
    assert result.cited_evidence_ids==['e1']
    path,payload=seen[0]
    assert path=='/api/chat' and payload['stream'] is False
    assert payload['format']==Synthesis.model_json_schema()
    assert payload['options']['temperature']==0

@pytest.mark.parametrize('response',[
    {'done':True,'message':{'content':'not json'}},
    {'done':True,'done_reason':'length','message':{'content':json.dumps(SYNTHESIS)}},
    {'done':False,'message':{'content':json.dumps(SYNTHESIS)}},
    {'done':True,'message':{'content':'{"draft":"missing fields"}'}}
])
def test_incomplete_or_malformed_chat_rejected(monkeypatch,response):
    monkeypatch.setattr(Ollama,'request',lambda *args,**kwargs:response)
    with pytest.raises(ValueError): Ollama().generate(Synthesis,'system',{})

def test_native_embedding_wiring_and_separate_collection(monkeypatch,tmp_path):
    import services.vectors as module
    from services.vectors import Vectors
    db=Database(tmp_path)
    original=Vectors(db).collection.name
    monkeypatch.setattr(module,'PROVIDER','ollama')
    monkeypatch.setattr(module,'ai_enabled',lambda:True)
    # Even if the model name is the same, providers must not share vectors.
    local=Vectors(db)
    assert local.collection.name!=original
    def request(self,path,payload):
        assert path=='/api/embed'
        assert payload['input']==['fixture one','fixture two']
        assert payload['truncate'] is False
        return {'embeddings':[[1.,0.],[0.,1.]]}
    monkeypatch.setattr(Ollama,'request',request)
    assert local.embed(['fixture one','fixture two'])==[[1.,0.],[0.,1.]]

@pytest.mark.parametrize('vectors',[[],[[1.]],[[1.,0.],[1.]],[[1.,float('nan')],[0.,1.]]])
def test_invalid_embeddings_rejected(monkeypatch,vectors):
    monkeypatch.setattr(Ollama,'request',lambda *args,**kwargs:{'embeddings':vectors})
    with pytest.raises(ValueError): Ollama().embed(['a','b'])

def test_connection_error_is_actionable(monkeypatch):
    def fail(*args,**kwargs): raise requests.ConnectionError('offline')
    monkeypatch.setattr(requests.Session,'post',fail)
    with pytest.raises(ValueError,match='ollama serve'):
        Ollama().generate(Synthesis,'system',{})

def test_model_status(monkeypatch):
    monkeypatch.setattr(Ollama,'request',lambda *args:{'models':[{'name':'llama3.1:8b'},{'name':'nomic-embed-text:latest'}]})
    import services.ollama as module
    monkeypatch.setattr(module,'MODEL','llama3.1:8b')
    monkeypatch.setattr(module,'EMBED_MODEL','nomic-embed-text')
    status=Ollama().status()
    assert status['chat_installed'] and status['embedding_installed']

def test_ollama_config_ui_without_openai_key(tmp_path):
    code='''
from core.config import ai_enabled, MODEL, MAX_AI_CHUNKS
from streamlit.testing.v1 import AppTest
assert ai_enabled() and MODEL=='llama3.1:8b' and MAX_AI_CHUNKS<=8
a=AppTest.from_file('app.py',default_timeout=30).run()
assert not a.exception
a.sidebar.radio[0].set_value('Tetapan').run()
assert not a.exception
assert any(b.label=='Uji sambungan Ollama' for b in a.button)
'''
    task_env=dict(os.environ,AI_PROVIDER='ollama',RESEARCHVAULT_DATA=str(tmp_path/'ui'))
    task_env.pop('OPENAI_API_KEY',None)
    result=subprocess.run([sys.executable,'-c',code],env=task_env,capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
