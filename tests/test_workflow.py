import io
import json
import sqlite3
import pymupdf
import pytest
from core.database import Database
from services.library import Library
from services.search import Search
from services.evidence import Evidence
from services.quote_verifier import verify_quote
from services.export import excel, matrix, bibtex
from services.ai import AI
from core.models import Relevance, Synthesis

@pytest.fixture
def db(tmp_path,monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    return Database(tmp_path/'data')

@pytest.fixture
def pdf():
    doc=pymupdf.open()
    doc.set_metadata({'title':'SYNTHETIC TEST FIXTURE — NOT REAL LITERATURE','author':'Test Fixture'})
    doc.new_page().insert_text((72,72),'Synthetic fixture only. This is not an academic publication.')
    doc.new_page().insert_text((72,72),'Perceived ease of use influences technology adoption. Government facilities require usable tools.')
    content=doc.tobytes(); doc.close(); return content

def test_upload_persistence_search_evidence_export(db,pdf):
    lib=Library(db)
    pid,created=lib.upload('../../paper.pdf',pdf)
    assert created
    assert lib.path(pid).parent==db.root/'uploads'
    assert lib.papers()[0]['filename']=='paper.pdf'
    assert lib.upload('copy.pdf',pdf)==(pid,False)
    # A second distinct PDF exercises multiple uploads.
    doc=pymupdf.open(); doc.new_page().insert_text((72,72),'Synthetic second fixture for facilities management.')
    pid2,_=lib.upload('second.pdf',doc.tobytes()); doc.close()
    lib.update(pid,year='2025',doi='10.1234/test',keywords='test')
    reopened=Database(db.root)
    assert len(Library(reopened).papers())==2
    results,warnings=Search(reopened).search('Effort Expectancy')
    assert results and results[0]['page_index']==1
    assert 'Perceived ease of use' in results[0]['verified_quote']
    assert verify_quote(results[0]['verified_quote'],results[0]['text'])
    eid=Evidence(reopened).save(results[0])
    Evidence(reopened).edit(eid,notes='Researcher note',section='2.1',construct='Effort Expectancy')
    saved=Evidence(Database(db.root)).all()
    assert saved[0]['notes']=='Researcher note' and saved[0]['page_index']==1
    import pandas as pd
    frame=pd.read_excel(io.BytesIO(excel(saved)))
    assert frame.iloc[0]['PDF Page']==2
    assert frame.iloc[0]['Thesis Section']==2.1
    assert '10.1234/test' in bibtex(lib.papers())
    assert Search(db).search('ease',paper_ids=[pid2])[0]==[]
    lib.delete(pid)
    assert not lib.path(pid).exists()
    assert not Evidence(db).all()
    assert Search(db).search('ease')[0]==[]

def test_quote_verification():
    source='The ease of inter-\naction improves\n usability.'
    assert verify_quote('The ease of interaction improves usability.',source)==source
    assert verify_quote('Invented evidence about adoption.',source) is None
    assert verify_quote('',source) is None

def test_reject_forged_evidence(db,pdf):
    Library(db).upload('fixture.pdf',pdf)
    row=Search(db).search('ease')[0][0]
    with pytest.raises(ValueError): Evidence(db).save(dict(row,verified_quote='Fabricated quotation that never existed.'))
    with pytest.raises(ValueError): Evidence(db).save(dict(row,page_index=0))

def test_validation_scans_and_profile(db):
    lib=Library(db)
    with pytest.raises(ValueError): lib.upload('bad.pdf',b'not pdf')
    with pytest.raises(ValueError): lib.path('../../escape')
    doc=pymupdf.open(); doc.new_page(); data=doc.tobytes(); doc.close()
    pid,_=lib.upload('scan.pdf',data)
    assert lib.papers()[0]['status']=='Requires OCR'
    assert Search(db).search('anything')[0]==[]
    profile=db.profile(); profile['title']='Edited'; db.save_profile(profile)
    assert Database(db.root).profile()['title']=='Edited'
    with pytest.raises(ValueError): AI(db).relevance(pid)

def test_missing_key_fallback(db,pdf):
    Library(db).upload('fixture.pdf',pdf)
    rows,warnings=Search(db).search('ease',mode='Hybrid')
    assert rows and warnings
    with pytest.raises(ValueError): AI(db).call(Relevance,{})

def test_doi_duplicate(db,pdf):
    lib=Library(db); pid,_=lib.upload('fixture.pdf',pdf)
    doc=pymupdf.open(); doc.new_page().insert_text((72,72),'Another synthetic fixture only.')
    pid2,_=lib.upload('other.pdf',doc.tobytes()); doc.close()
    lib.update(pid,doi='10.1234/example')
    with pytest.raises(sqlite3.IntegrityError): lib.update(pid2,doi='https://doi.org/10.1234/EXAMPLE')

def test_ai_grounding_contract(db,pdf,monkeypatch):
    pid,_=Library(db).upload('fixture.pdf',pdf)
    row=Search(db).search('ease')[0][0]
    assessment=dict(category='High',score=80,explanation='Fixture assessment only',constructs=['Effort Expectancy'],thesis_sections=['2'],contributions=[],limitations=['Synthetic fixture'],supporting_passages=[dict(chunk_id=row['id'],quote=row['verified_quote'],classification='Supporting',interpretation='Test',construct='Effort Expectancy')])
    agent=AI(db)
    monkeypatch.setattr(agent,'call',lambda schema,payload:Relevance(**assessment))
    result=agent.relevance(pid)
    assert result['supporting_passages'][0]['quote']==row['verified_quote']
    assert result['source_pages'][row['id']]==2
    assessment['supporting_passages'][0]['quote']='A completely invented claim that is absent.'
    with pytest.raises(ValueError): agent.relevance(pid)
    eid=Evidence(db).save(row)
    monkeypatch.setattr(agent,'call',lambda schema,payload:Synthesis(draft='test',similarities=[],differences=[],limitations=[],cited_evidence_ids=['unknown']))
    with pytest.raises(ValueError): agent.synthesize(Evidence(db).all(),'test')

def test_spreadsheet_injection():
    row=dict(authors='=CMD()',page_index=0,verified_quote='+SUM(1,1)')
    assert matrix([row]).iloc[0]['Authors'].startswith("'")

def test_vector_persistence_and_cache(db,pdf,monkeypatch):
    from services.vectors import Vectors
    pid,_=Library(db).upload('fixture.pdf',pdf)
    calls=[]
    def embedding(self,texts):
        calls.extend(texts)
        return [[float('ease' in t.lower()),1.0,0.5] for t in texts]
    monkeypatch.setattr(Vectors,'embed',embedding)
    vector=Vectors(db)
    assert vector.index(pid)==2
    assert len(calls)==2
    vector.index(pid)
    assert len(calls)==2
    assert Vectors(Database(db.root)).search('ease')
    assert Vectors(db).indexed_papers()=={pid}
    Library(db).delete(pid)
    assert not Vectors(db).indexed_papers()

def test_hybrid_vector_search_and_partial_index(db,pdf,monkeypatch):
    from services.vectors import Vectors
    import services.search as search_module
    pid,_=Library(db).upload('fixture.pdf',pdf)
    def embedding(self,texts):
        return [[float('ease' in t.lower()),1.0,0.5] for t in texts]
    monkeypatch.setattr(Vectors,'embed',embedding)
    monkeypatch.setattr(search_module,'ai_enabled',lambda:True)
    v=Vectors(db)
    v.index(pid)
    rows,warnings=Search(db).search('ease',mode='Hybrid')
    assert rows and not warnings
    assert rows[0]['page_index']==1
    chunk=db.rows('SELECT id FROM chunks WHERE paper_id=? LIMIT 1',(pid,))[0]['id']
    v.collection.delete(ids=[chunk])
    assert pid not in v.indexed_papers()
    v.index(pid)
    assert pid in v.indexed_papers()

def test_crossref_metadata_contract(db,pdf,monkeypatch):
    import services.library as module
    pid,_=Library(db).upload('fixture.pdf',pdf)
    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {'message':{'DOI':'10.1234/test','title':['SYNTHETIC CROSSREF RESPONSE'],
                'author':[{'given':'Synthetic','family':'Fixture'}],
                'published':{'date-parts':[[2025]]},'container-title':['TEST ONLY']}}
    seen=[]
    def get(url,timeout):
        seen.append(url)
        assert timeout==20
        return Response()
    monkeypatch.setattr(module.requests,'get',get)
    Library(db).crossref(pid,'10.1234/test')
    assert Library(db).papers()[0]['title']=='SYNTHETIC CROSSREF RESPONSE'
    assert seen[0].startswith('https://api.crossref.org/works/')
