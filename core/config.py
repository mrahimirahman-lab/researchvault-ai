import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
DATA = Path(os.getenv('RESEARCHVAULT_DATA', 'data')).resolve()
PROVIDER = os.getenv('AI_PROVIDER', 'openai').strip().lower()
if PROVIDER not in {'openai', 'ollama'}:
    raise ValueError('AI_PROVIDER must be openai or ollama')
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/')
MODEL = os.getenv('OLLAMA_MODEL', 'llama3.1:8b') if PROVIDER == 'ollama' else os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')
EMBED_MODEL = os.getenv('OLLAMA_EMBEDDING_MODEL', 'nomic-embed-text') if PROVIDER == 'ollama' else os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small')
OLLAMA_NUM_CTX = max(2048, int(os.getenv('OLLAMA_NUM_CTX', '8192')))
CHUNK_SIZE = max(200, int(os.getenv('CHUNK_SIZE', '1200')))
OVERLAP = min(CHUNK_SIZE // 2, max(0, int(os.getenv('CHUNK_OVERLAP', '200'))))
MAX_UPLOAD = int(os.getenv('MAX_UPLOAD_MB', '30')) * 1024 * 1024
MAX_AI_CHUNKS = max(1, int(os.getenv('MAX_AI_CHUNKS', '24')))
if PROVIDER == 'ollama':
    MAX_AI_CHUNKS = min(MAX_AI_CHUNKS, max(1, int(os.getenv('OLLAMA_MAX_AI_CHUNKS', '8'))))

def has_key():
    return bool(os.getenv('OPENAI_API_KEY', '').strip())

def ai_enabled():
    # Configured is not the same as connected: use Settings to test Ollama.
    return PROVIDER == 'ollama' or has_key()
