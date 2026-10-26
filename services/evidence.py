import uuid
from services.quote_verifier import verify_quote

class Evidence:
    def __init__(self, db):
        self.db = db

    def save(self, row):
        source = self.db.rows('SELECT * FROM chunks WHERE id=?',(row['source_chunk_id'],))
        if not source or source[0]['paper_id'] != row['paper_id'] or source[0]['page_index'] != row['page_index']:
            raise ValueError('Invalid evidence provenance')
        quote = verify_quote(row['verified_quote'],source[0]['text'])
        if not quote:
            raise ValueError('Quotation verification failed')
        eid = uuid.uuid4().hex
        self.db.execute('''INSERT INTO evidence(id,paper_id,page_index,source_chunk_id,verified_quote,
            verification_status,construct,classification,interpretation) VALUES(?,?,?,?,?,?,?,?,?)''',
            (eid,row['paper_id'],row['page_index'],row['source_chunk_id'],quote,'Verified',
             row.get('construct',''),row.get('classification','Inconclusive'),row.get('interpretation','')))
        return eid

    def all(self):
        return self.db.rows('''SELECT e.*,p.title,p.authors,p.year,p.journal,p.doi FROM evidence e
                              JOIN papers p ON p.id=e.paper_id ORDER BY saved DESC''')

    def edit(self,eid,**fields):
        if not fields or not set(fields) <= {'construct','theme','classification','interpretation','notes','chapter','section'}:
            raise ValueError('Unsupported evidence field')
        self.db.execute('UPDATE evidence SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',(*fields.values(),eid))
