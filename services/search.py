import re
from core.config import has_key
from services.quote_verifier import verify_quote

class Search:
    def __init__(self, db):
        self.db = db

    def search(self, query, mode='Keyword', limit=10, paper_ids=None, author='', year='', construct=''):
        if not query.strip():
            return [], []
        expanded = query
        constructs = self.db.profile()['constructs']
        for name, synonyms in constructs.items():
            if name.lower() in query.lower() or construct == name:
                expanded += ' ' + ' '.join(synonyms) + ' ' + name
        words = list(dict.fromkeys(re.findall(r'\w+',expanded)))[:80]
        match = ' OR '.join('"'+w+'"' for w in words if len(w)>2)
        filters, params = [], []
        if paper_ids:
            filters.append('p.id IN ('+','.join('?' for _ in paper_ids)+')')
            params.extend(paper_ids)
        if author:
            filters.append('lower(p.authors) LIKE ?'); params.append('%'+author.lower()+'%')
        if year:
            filters.append('p.year=?'); params.append(year)
        clause = (' AND '+' AND '.join(filters)) if filters else ''
        base = '''SELECT c.*,p.title,p.authors,p.year,p.journal,p.doi,p.filename
                  FROM chunks c JOIN papers p ON p.id=c.paper_id'''
        lexical = []
        if match:
            lexical = self.db.rows(base+' JOIN chunks_fts f ON f.id=c.id WHERE chunks_fts MATCH ?'+clause+
                                   ' ORDER BY bm25(chunks_fts) LIMIT 200',(match,*params))
        warnings, semantic = [], []
        if mode != 'Keyword':
            if not has_key():
                warnings.append('AI key unavailable: showing keyword results only.')
            else:
                try:
                    from services.vectors import Vectors
                    ids = Vectors(self.db).search(expanded,100)
                    # Join back to SQLite: stale or deleted vectors never become evidence.
                    for cid in ids:
                        semantic.extend(self.db.rows(base+' WHERE c.id=?'+clause,(cid,*params)))
                except Exception as exc:
                    warnings.append(f'Semantic search unavailable: {exc}. Keyword fallback used.')
        ranks, records = {}, {}
        lists = [lexical] if mode == 'Keyword' or not semantic else [semantic] if mode == 'Semantic' else [lexical,semantic]
        for results in lists:
            for rank, row in enumerate(results):
                records[row['id']] = row
                ranks[row['id']] = ranks.get(row['id'],0) + 1/(60+rank+1)
        output = []
        for cid in sorted(ranks,key=ranks.get,reverse=True):
            row = records[cid]
            # A source substring is the quote; ranking is not evidence classification.
            sentences = re.split(r'(?<=[.!?])\s+',row['text'])
            candidates = [s for s in sentences if 10 <= len(s.strip()) <= 700]
            candidate = max(candidates,key=lambda s:sum(w.lower() in s.lower() for w in words),default=row['text'][:500])
            quote = verify_quote(candidate,row['text'])
            if not quote:
                continue
            row.update(source_chunk_id=cid,verified_quote=quote,verification_status='Verified',
                       construct=construct,classification='Inconclusive',interpretation='',score=ranks[cid])
            output.append(row)
            if len(output) >= limit:
                break
        return output, warnings
