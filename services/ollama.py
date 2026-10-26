"""Local Ollama transport. No OpenAI credential or cloud fallback."""
import json
import math
from urllib.parse import urlsplit
import requests
from pydantic import ValidationError
from core.config import OLLAMA_BASE_URL, MODEL, EMBED_MODEL, OLLAMA_NUM_CTX

class Ollama:
    def __init__(self, base_url=OLLAMA_BASE_URL):
        parsed = urlsplit(base_url)
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('OLLAMA_BASE_URL must be an HTTP(S) server URL without credentials')
        self.base_url = base_url.rstrip('/')

    def request(self, path, payload=None):
        # Local traffic must not leave through an ambient corporate/cloud proxy.
        session = requests.Session()
        session.trust_env = False
        try:
            with session:
                response = session.get(self.base_url+path, timeout=(5, 15)) if payload is None else session.post(self.base_url+path,json=payload,timeout=(5, 300))
                response.raise_for_status()
                result = response.json()
                if not isinstance(result,dict):
                    raise ValueError('Ollama returned an invalid response')
                if result.get('error'):
                    raise ValueError('Ollama: '+str(result['error']))
                return result
        except requests.ConnectionError as exc:
            raise ValueError('Tidak dapat sambung ke Ollama. Buka aplikasi Ollama, atau jalankan ollama serve. Semak OLLAMA_BASE_URL.') from exc
        except requests.Timeout as exc:
            raise ValueError('Ollama mengambil terlalu lama. Pilih kurang evidence atau cuba model lebih kecil.') from exc
        except requests.HTTPError as exc:
            code=exc.response.status_code
            raise ValueError(f'Ollama HTTP {code}. Semak ollama list; pastikan model {MODEL} dan {EMBED_MODEL} sudah dimuat turun. Rujuk README untuk arahan ollama pull.') from exc

    def generate(self, schema, system, payload):
        result = self.request('/api/chat', {
            'model': MODEL, 'stream': False,
            'messages': [{'role':'system','content':system+' Return JSON matching the provided schema.'},
                         {'role':'user','content':json.dumps(payload)}],
            'format': schema.model_json_schema(),
            'options': {'temperature':0, 'num_ctx':OLLAMA_NUM_CTX, 'num_predict':2500},
        })
        if result.get('done') is not True or result.get('done_reason') == 'length':
            raise ValueError('Ollama response incomplete. Select fewer evidence records and retry.')
        try:
            return schema.model_validate_json(result['message']['content'])
        except (KeyError, TypeError, ValidationError) as exc:
            raise ValueError('Ollama returned invalid structured output. No result saved; retry with fewer evidence records.') from exc

    def embed(self, texts):
        result = self.request('/api/embed', {'model':EMBED_MODEL,'input':texts,'truncate':False})
        vectors=result.get('embeddings')
        if not isinstance(vectors,list) or len(vectors)!=len(texts) or not vectors:
            raise ValueError('Ollama embedding count mismatch')
        dimension=len(vectors[0]) if isinstance(vectors[0],list) else 0
        if not dimension or any(not isinstance(v,list) or len(v)!=dimension or any(isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n) for n in v) for v in vectors):
            raise ValueError('Ollama returned invalid embedding vectors')
        return vectors

    def status(self):
        installed={m['name'] for m in self.request('/api/tags').get('models',[]) if 'name' in m}
        def present(model):
            return model in installed or (':' not in model and model+':latest' in installed)
        return {'server':'connected','chat_model':MODEL,'chat_installed':present(MODEL),
                'embedding_model':EMBED_MODEL,'embedding_installed':present(EMBED_MODEL)}
