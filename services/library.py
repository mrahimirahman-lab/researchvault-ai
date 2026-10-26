import hashlib
import logging
import re
import uuid
from pathlib import Path
import pymupdf
import requests
from core.config import CHUNK_SIZE, OVERLAP, MAX_UPLOAD

logger = logging.getLogger(__name__)

class Library:
    def __init__(self, db):
        self.db = db

    def papers(self):
        return self.db.rows('SELECT * FROM papers ORDER BY uploaded DESC')

    def path(self, paper_id):
        # All disk paths use internal UUIDs; never uploaded filenames.
        if not re.fullmatch(r'[a-f0-9]{32}', paper_id):
            raise ValueError('Invalid paper ID')
        return self.db.root / 'uploads' / f'{paper_id}.pdf'

    def upload(self, filename, content):
        if not filename.lower().endswith('.pdf') or not content.startswith(b'%PDF-'):
            raise ValueError('Only PDF files are accepted')
        if len(content) > MAX_UPLOAD:
            raise ValueError('PDF exceeds configured upload limit')
        digest = hashlib.sha256(content).hexdigest()
        existing = self.db.rows('SELECT id FROM papers WHERE hash=?', (digest,))
        if existing:
            return existing[0]['id'], False
        with pymupdf.open(stream=content, filetype='pdf') as doc:
            if doc.needs_pass:
                raise ValueError('Password-protected PDFs are unsupported')
            if not len(doc):
                raise ValueError('PDF has no pages')
        paper_id = uuid.uuid4().hex
        safe_name = Path(filename.replace('\\', '/')).name
        self.path(paper_id).write_bytes(content)
        try:
            self.db.execute('INSERT INTO papers(id,hash,filename,title,status) VALUES(?,?,?,?,?)',
                            (paper_id,digest,safe_name,Path(safe_name).stem,'Pending'))
        except Exception:
            self.path(paper_id).unlink(missing_ok=True)
            raise
        self.process(paper_id)
        return paper_id, True

    def process(self, paper_id):
        # Stable chunks are reused on retries; saved evidence is never invalidated.
        if self.db.rows('SELECT id FROM chunks WHERE paper_id=? LIMIT 1', (paper_id,)):
            return
        try:
            with pymupdf.open(self.path(paper_id)) as doc:
                metadata = doc.metadata or {}
                texts = [page.get_text(sort=True) for page in doc]
                scanned = [i + 1 for i,t in enumerate(texts) if len(t.strip()) < 20]
                status = 'Requires OCR' if len(scanned) == len(texts) else 'Partial — OCR required' if scanned else 'Extracted'
                with self.db.connect() as c:
                    for page_index, text in enumerate(texts):
                        for start in range(0, len(text), CHUNK_SIZE - OVERLAP):
                            part = text[start:start + CHUNK_SIZE]
                            if part.strip():
                                chunk_id = f'{paper_id}:{page_index}:{start}'
                                c.execute('INSERT INTO chunks VALUES(?,?,?,?)', (chunk_id,paper_id,page_index,part))
                    c.execute('UPDATE papers SET title=?,authors=?,pages=?,status=?,error=? WHERE id=?',
                              (metadata.get('title') or self.db.rows('SELECT title FROM papers WHERE id=?',(paper_id,))[0]['title'],
                               metadata.get('author') or '',len(doc),status,
                               f'Pages requiring OCR review: {scanned}' if scanned else '',paper_id))
        except Exception as exc:
            logger.exception('PDF processing failed for %s', paper_id)
            self.db.execute("UPDATE papers SET status='Failed',error=? WHERE id=?",(str(exc),paper_id))
            raise

    def update(self, paper_id, **fields):
        allowed = {'title','authors','year','journal','doi','abstract','keywords','metadata_status'}
        if not fields or not set(fields) <= allowed:
            raise ValueError('Unsupported metadata field')
        if 'doi' in fields:
            fields['doi'] = re.sub(r'^https?://(?:dx\.)?doi.org/', '', fields['doi'].strip(), flags=re.I).lower()
        self.db.execute('UPDATE papers SET '+','.join(f'{k}=?' for k in fields)+' WHERE id=?', (*fields.values(),paper_id))

    def crossref(self, paper_id, doi):
        from urllib.parse import quote
        doi = re.sub(r'^https?://(?:dx\.)?doi.org/', '', doi.strip(), flags=re.I)
        if not re.fullmatch(r'10\.\d{4,9}/\S+', doi):
            raise ValueError('Enter a valid DOI')
        response = requests.get('https://api.crossref.org/works/'+quote(doi,safe=''), timeout=20)
        response.raise_for_status()
        m = response.json()['message']
        if m.get('DOI','').lower() != doi.lower():
            raise ValueError('Crossref DOI did not match')
        dates = m.get('published',{}).get('date-parts',[[]])[0]
        self.update(paper_id, title='; '.join(m.get('title',[])) or 'Not available',
                    authors='; '.join(' '.join([a.get('given',''),a.get('family','')]).strip() for a in m.get('author',[])),
                    year=str(dates[0]) if dates else '', journal='; '.join(m.get('container-title',[])),
                    doi=m['DOI'], metadata_status='Crossref verified (DOI; confirm document match)')

    def delete(self, paper_id):
        from services.vectors import Vectors
        # If an existing vector index cannot be cleaned, keep the paper for retry.
        if (self.db.root / 'chroma').exists():
            Vectors(self.db).delete(paper_id)
        self.db.execute('DELETE FROM papers WHERE id=?',(paper_id,))
        self.path(paper_id).unlink(missing_ok=True)
