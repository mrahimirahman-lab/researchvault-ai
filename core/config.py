import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
DATA = Path(os.getenv('RESEARCHVAULT_DATA', 'data')).resolve()
MODEL = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')
EMBED_MODEL = os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small')
CHUNK_SIZE = max(200, int(os.getenv('CHUNK_SIZE', '1200')))
OVERLAP = min(CHUNK_SIZE // 2, max(0, int(os.getenv('CHUNK_OVERLAP', '200'))))
MAX_UPLOAD = int(os.getenv('MAX_UPLOAD_MB', '30')) * 1024 * 1024
MAX_AI_CHUNKS = max(1, int(os.getenv('MAX_AI_CHUNKS', '24')))

def has_key():
    return bool(os.getenv('OPENAI_API_KEY', '').strip())
