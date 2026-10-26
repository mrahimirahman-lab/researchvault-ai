"""Exercise every page in a separate process and isolated, temporary data directory."""
import os
import subprocess
import sys


def test_streamlit_pages(tmp_path):
    code = '''
import pymupdf
from streamlit.testing.v1 import AppTest
from core.database import Database
from services.library import Library
from services.search import Search
from services.evidence import Evidence

db=Database()
doc=pymupdf.open()
doc.new_page().insert_text((72,72),'SYNTHETIC TEST ONLY. Perceived ease of use influences technology adoption.')
Library(db).upload('synthetic-ui-fixture.pdf',doc.tobytes())
doc.close()
row=Search(db).search('ease')[0][0]
Evidence(db).save(row)
a=AppTest.from_file('app.py',default_timeout=30).run()
assert not a.exception, a.exception
for page in ['Pustaka Kertas','AI Evidence Finder','Construct Explorer','Evidence Bank','AI Literature Synthesis','Profil Penyelidikan','Tetapan','Dashboard']:
    a.sidebar.radio[0].set_value(page).run()
    assert not a.exception, (page,a.exception)
a.sidebar.radio[0].set_value('AI Evidence Finder').run()
a.text_input[0].set_value('Effort Expectancy')
next(b for b in a.button if b.label=='Cari Evidence').click().run()
assert not a.exception, a.exception
assert any('Perceived ease of use' in t.value for t in a.text)
next(b for b in a.button if b.label=='Simpan Evidence').click().run()
assert not a.exception
assert len(Evidence(db).all())==2
'''
    task_env = dict(os.environ, RESEARCHVAULT_DATA=str(tmp_path/'ui-data'))
    task_env.pop('OPENAI_API_KEY',None)
    result=subprocess.run([sys.executable,'-c',code],env=task_env,capture_output=True,text=True,timeout=90)
    assert result.returncode==0, result.stdout+result.stderr
