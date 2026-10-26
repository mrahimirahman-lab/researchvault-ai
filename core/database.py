import json
import sqlite3
from contextlib import contextmanager
from core.config import DATA

DEFAULT_PROFILE = {
    'title': 'Developing a Data-Driven Facilities Management Model Towards Evidence-Based Practice in the Malaysian Government Sector.',
    'background': '', 'problem': '', 'questions': '', 'objectives': '', 'methodology': '',
    'framework': 'Integrated UTAUT and Technology-Organization-Environment (TOE)',
    'constructs': {
        'Performance Expectancy': ['perceived usefulness'],
        'Effort Expectancy': ['perceived ease of use', 'ease of learning', 'user friendliness', 'ease of interaction', 'perceived complexity', 'usability'],
        'Social Influence': [], 'Facilitating Conditions': [], 'Technology Readiness': [],
        'Organizational Support': [], 'External Environment': [],
        'Data-Driven Facilities Management Practice': ['DDFM']},
    'definitions': '',
    'outcomes': 'Informed Decision-Making; Predictive Maintenance; Operational Efficiency; Proactive Resource Planning; Accountability and Transparency',
    'keywords': 'Facilities Management, Malaysian Government, evidence-based practice'
}

class Database:
    def __init__(self, root=DATA):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        (root / 'uploads').mkdir(exist_ok=True)
        self.path = root / 'researchvault.sqlite3'
        with self.connect() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS papers (
                id TEXT PRIMARY KEY, hash TEXT UNIQUE NOT NULL, filename TEXT NOT NULL,
                title TEXT NOT NULL, authors TEXT DEFAULT '', year TEXT DEFAULT '',
                journal TEXT DEFAULT '', doi TEXT DEFAULT '', abstract TEXT DEFAULT '',
                keywords TEXT DEFAULT '', metadata_status TEXT DEFAULT 'Not verified',
                uploaded TEXT DEFAULT CURRENT_TIMESTAMP, pages INTEGER DEFAULT 0,
                status TEXT NOT NULL, error TEXT DEFAULT '', assessment TEXT DEFAULT '');
            CREATE UNIQUE INDEX IF NOT EXISTS unique_doi ON papers(lower(doi)) WHERE doi != '';
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY, paper_id TEXT REFERENCES papers(id) ON DELETE CASCADE,
                page_index INTEGER NOT NULL, text TEXT NOT NULL);
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(id UNINDEXED, text);
            CREATE TRIGGER IF NOT EXISTS chunk_insert AFTER INSERT ON chunks BEGIN
                INSERT INTO chunks_fts(id,text) VALUES(new.id,new.text); END;
            CREATE TRIGGER IF NOT EXISTS chunk_delete AFTER DELETE ON chunks BEGIN
                DELETE FROM chunks_fts WHERE id=old.id; END;
            CREATE TABLE IF NOT EXISTS evidence (
                id TEXT PRIMARY KEY, paper_id TEXT REFERENCES papers(id) ON DELETE CASCADE,
                page_index INTEGER NOT NULL, source_chunk_id TEXT REFERENCES chunks(id) ON DELETE CASCADE,
                verified_quote TEXT NOT NULL, verification_status TEXT NOT NULL,
                construct TEXT DEFAULT '', theme TEXT DEFAULT '', classification TEXT DEFAULT 'Inconclusive',
                interpretation TEXT DEFAULT '', notes TEXT DEFAULT '', chapter TEXT DEFAULT '', section TEXT DEFAULT '',
                saved TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            ''')
            c.execute('INSERT OR IGNORE INTO settings VALUES (?,?)', ('profile', json.dumps(DEFAULT_PROFILE)))

    @contextmanager
    def connect(self):
        c = sqlite3.connect(self.path, timeout=30)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    def rows(self, sql, args=()):
        with self.connect() as c:
            return [dict(r) for r in c.execute(sql, args)]

    def execute(self, sql, args=()):
        with self.connect() as c:
            c.execute(sql, args)

    def profile(self):
        return json.loads(self.rows("SELECT value FROM settings WHERE key='profile'")[0]['value'])

    def save_profile(self, value):
        self.execute("UPDATE settings SET value=? WHERE key='profile'", (json.dumps(value),))
