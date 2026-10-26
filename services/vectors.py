import hashlib
from core.config import EMBED_MODEL, ai_enabled, PROVIDER

class Vectors:
    def __init__(self, db):
        import chromadb
        self.db = db
        self.client = chromadb.PersistentClient(path=str(db.root / 'chroma'))
        self.collection = self.client.get_or_create_collection(
            'papers_'+hashlib.sha256((EMBED_MODEL if PROVIDER == 'openai' else PROVIDER+':'+EMBED_MODEL).encode()).hexdigest()[:12],
            metadata={'hnsw:space':'cosine'})

    def embed(self, texts):
        if not ai_enabled():
            raise ValueError('OPENAI_API_KEY is not configured')
        if PROVIDER == 'ollama':
            from services.ollama import Ollama
            return Ollama().embed(texts)
        from openai import OpenAI
        result = OpenAI().embeddings.create(model=EMBED_MODEL,input=texts)
        return [r.embedding for r in result.data]

    def index(self, paper_id):
        chunks = self.db.rows('SELECT * FROM chunks WHERE paper_id=?',(paper_id,))
        existing = set(self.collection.get(where={'paper_id':paper_id})['ids'])
        pending = [c for c in chunks if c['id'] not in existing]
        for start in range(0,len(pending),32):
            batch = pending[start:start+32]
            embeddings = self.embed([c['text'] for c in batch])
            self.collection.upsert(ids=[c['id'] for c in batch],embeddings=embeddings,
                metadatas=[{'paper_id':paper_id,'page_index':c['page_index']} for c in batch])
        return len(chunks)

    def search(self, query, n=30):
        count = self.collection.count()
        if not count:
            return []
        result = self.collection.query(query_embeddings=self.embed([query]),n_results=min(n,count))
        return result['ids'][0]

    def delete(self, paper_id):
        # Clean all embedding model collections, including previously configured models.
        for collection in self.client.list_collections():
            self.client.get_collection(collection.name).delete(where={'paper_id':paper_id})

    def indexed_papers(self):
        indexed = set(self.collection.get()['ids'])
        groups = {}
        for row in self.db.rows('SELECT id,paper_id FROM chunks'):
            groups.setdefault(row['paper_id'], set()).add(row['id'])
        return {paper_id for paper_id, chunks in groups.items() if chunks <= indexed}
