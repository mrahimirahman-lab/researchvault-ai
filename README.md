# ResearchVault AI

A single-user, local-first Streamlit application for managing research PDFs and building a source-verifiable literature evidence bank. Navigation is primarily Bahasa Melayu. Original PDFs, extracted text, metadata, profiles, evidence and embeddings stay on disk. AI operations send relevant extracted text to the configured OpenAI or Ollama provider only when explicitly requested. DOI validation sends the DOI to Crossref.

## Windows PowerShell installation

Install 64-bit Python 3.11 or later (Python 3.12 recommended), then open PowerShell in this project folder:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m pytest -q
.\start.bat
```

No PowerShell activation or execution-policy change is needed. If you have Python 3.11 instead, substitute `py -3.11`. The equivalent launch command is:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Open the local address printed by Streamlit in your browser. Keep the terminal open; Ctrl+C stops the app. `start.bat` always starts from the project directory. Windows commands are documented but have not been run on Windows in the development environment.

On Linux/macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1
```

## Free local AI with Ollama (Windows)

OpenAI is optional. For local Llama inference with no paid API, install the current Windows version of [Ollama](https://ollama.com/download/windows). Start Ollama, reopen PowerShell and run:

```powershell
ollama pull llama3.1:8b
ollama pull nomic-embed-text
ollama list
```

These downloads require several GB and Internet access once. Llama 3.1 8B's default quantized model is a reasonable starting point for a Windows PC with 32 GB RAM and an RTX 4060 Laptop GPU (8 GB). It may offload some work to CPU depending on available VRAM/context length. Actual speed and model quality must be checked on your machine. Local inference has no provider API charges, but uses your computer's resources.

Keep the existing `.env`; add or update these lines (one entry per name):

```dotenv
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.1:8b
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_NUM_CTX=8192
OLLAMA_MAX_AI_CHUNKS=8
```

Stop Streamlit with Ctrl+C and run `start.bat` again. Open **Tetapan → Uji sambungan Ollama**. Both `chat_installed` and `embedding_installed` should be true. Ollama must remain running alongside Streamlit. If it is not running, open the Ollama application, or run `ollama serve` in a separate terminal. Do not start another server if Ollama is already using port 11434.

Then select saved evidence in **AI Literature Synthesis** and click **Jana draf sintesis**. Start with 2–4 records; local generation can take time. The initial local limit is eight records per request. Paper relevance and passage classification use the same local model. No OpenAI key is needed. The UI enables local operations when Ollama is configured, but connection/model checks are required to establish runtime readiness. Invalid JSON, truncated responses and unverified quotations are rejected rather than saved as successful results.

For semantic search, explicitly select papers and run **Index Semantic — pilihan** again with Ollama. Local embeddings use a separate collection from OpenAI; existing OpenAI vectors cannot be queried with the local model. Your PDFs, evidence bank and SQLite metadata are unchanged. Relevance assessments saved previously remain available; rerun them if you want a new assessment from the local model. Changing a model's underlying weights under the same name requires a new model tag/collection or deliberate reindexing; the app caches by provider and configured model name.

With the default loopback URL, AI passage text stays on this computer. Configuring a remote Ollama URL sends text to that host. DOI lookup still uses Crossref over the Internet. Ollama calls never silently fall back to OpenAI. Native `/api/chat` structured output and `/api/embed` require a current Ollama installation. Generation is limited to 2,500 output tokens and requests time out after five minutes. Reduce evidence selection if generation is slow or incomplete. Small local models can produce weaker synthesis than larger hosted models: verify citations, claims and original quotations yourself.

To update an existing ZIP installation, stop Streamlit and copy only the updated `app.py`, `core` and `services` source folders into your existing project, replacing source files. Do **not** replace `.env`, `.venv` or `data`. No new Python dependencies are required for Ollama support.

## Configuration

Edit `.env` locally. Put your own `OPENAI_API_KEY` there, never in source code or Git. The application does not display the key. Restart the Streamlit process after changing configuration. An existing process environment variable takes precedence over `.env`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | empty | Enables OpenAI operations; optional for the local workflow |
| `OPENAI_MODEL` | `gpt-4.1-mini` | Model supporting structured outputs |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model; each model has a separate local collection |
| `RESEARCHVAULT_DATA` | `data` | Persistent data directory; relative to working directory |
| `CHUNK_SIZE` | `1200` | Maximum characters per page-bound chunk |
| `CHUNK_OVERLAP` | `200` | Overlap between chunks on one page |
| `MAX_UPLOAD_MB` | `30` | Per-file upload limit |
| `MAX_AI_CHUNKS` | `24` | Maximum passages per relevance/synthesis request |

The installed direct dependency versions are pinned. Transitive dependencies are resolved by pip; this is not a cross-platform transitive lockfile. Cloud development was validated on Python 3.12/Linux. OpenAI and Crossref need outbound HTTPS to `api.openai.com` and `api.crossref.org`. No AI key is required to run tests. On cloud platforms that reserve `OPENAI_*` secret names, this app still requires an appropriately injected runtime variable or a private local `.env`; do not put a key into a saved setup script.

## Workflow

1. **Profil Penyelidikan**: edit the demonstration title, framework, constructs and related terms. Fill in your own background, questions, objectives, definitions and methodology. Save the profile. Construct synonyms are editable JSON mapping names to lists of related terms. There is one active local profile. New profiles do not automatically recompute old relevance assessments; stale assessments are flagged.
2. **Pustaka Kertas**: select multiple PDFs and choose **Proses semua PDF**. Upload validates the PDF header, type, size, password status and page count. Files are stored under permanent UUIDs, never user-controlled paths. SHA-256 duplicates reuse the existing record. Unknown bibliographic fields stay blank/Not available, and extracted metadata is Not verified.
3. Edit title/authors/year/DOI/keywords manually. **Semak DOI dengan Crossref** validates an explicitly entered DOI and retrieves its metadata. Confirm it actually describes the uploaded document: validating a DOI alone does not prove that match. Duplicate DOIs are rejected. Automatic DOI inference is not implemented.
4. Pages are extracted with PyMuPDF and indexed in SQLite FTS5. Image-only/very-low-text pages are flagged for OCR review, with their page numbers. OCR is not implemented. Failed documents remain visible and can be retried. Existing successful chunks are retained on retry to preserve evidence references.
5. With your AI provider configured, select papers and click **Index Semantic — pilihan**. This is an explicit opt-in operation: OpenAI requires a paid API key, whereas Ollama uses the configured local embedding model. It generates embeddings in batches and persists them in ChromaDB. Existing chunk IDs are skipped, so retries do not repeat successful embeddings. Index all papers you want to include in semantic search. Changing embedding model requires explicitly indexing again. Keyword search remains available before this step.
6. Use **Analyze Relevance** individually or in bulk. Assessments use the active profile and at most `MAX_AI_CHUNKS` sampled passages, evenly spread across long documents. The result includes coverage, source chunk IDs and physical PDF page references. Supporting quotations are verified; an invalid quotation rejects the result. Scores are AI heuristics, not validated measurements. A structurally valid assessment is still a researcher-reviewable interpretation.
7. **AI Evidence Finder**: choose Keyword, Hybrid or Semantic retrieval, query and optional paper/author/year/construct context. Hybrid uses reciprocal-rank fusion over FTS and vector results. User-defined related terms expand queries. **Construct Explorer** starts a search from a selected construct. Related terms do not establish theoretical equivalence. A construct selection supplies search context, not a guaranteed classifier. Exact evidence and conceptual modes share source verification; conceptual retrieval requires semantic/hybrid selection. Cross-paper mode guides you to save and select evidence before synthesis.
8. Search results show **actual extracted source text**, metadata and the physical PDF page number. Open **Buka PDF asal** to view the embedded original PDF at that page. Native PDF embedding depends on browser support; a download fallback is provided with the required page number. Printed page numbers and section names are not inferred. Always inspect surrounding context yourself.
9. Search ranking does not establish whether a passage supports your claim. Default classification is Inconclusive. Use **Klasifikasi AI** to obtain a separately labelled interpretation, then choose to save that classified result. AI quotation candidates must match the stored source. Manual classification and construct correction are available in the bank.
10. **Simpan Evidence** creates a persistent evidence record. In **Evidence Bank**, add your own notes, construct, theme, chapter and section. Filter the Literature Evidence Matrix and export Excel/CSV. Source IDs and verification status are included. Spreadsheet formula-like text is escaped in exports for safety.
11. **AI Literature Synthesis**: select saved evidence and enter a question. Quotes are reverified before use; unknown structured source IDs are rejected. The model is instructed to compare only selected sources and distinguish theory, findings and interpretations. The draft and referenced evidence IDs are shown. All generated claims and inline references still require manual checking; this is not an automated proof of entailment.
12. BibTeX export includes only records with title, authors and year. It does not certify bibliographic accuracy. Enter multiple authors separated by semicolons for the basic exporter.

## Provenance and limitations

Every evidence record retains `paper_id`, zero-based `page_index`, `source_chunk_id`, `verified_quote` and `verification_status`. Displayed pages are `page_index + 1`. Verification normalizes whitespace, Unicode compatibility forms and end-of-line hyphenation for matching, then returns the **original source substring**, preserving its wording. Direct quotations are short page-bound passages. No web literature is silently added. PDF text is treated as untrusted data in AI prompts.

Retrieval is limited to the top candidate chunks (up to 200 lexical and 100 vector candidates), then filtered and ranked. Narrow filters may miss vector candidates outside that pool. Search results and sampled relevance assessments must never be represented as exhaustive library coverage. Extracted PDF reading order can be imperfect, especially for columns, tables and scans. A verified text match proves provenance, not the quality, relevance, or truth of a claim. Review the original PDF.

In OpenAI mode without a key, AI buttons are disabled and hybrid/semantic requests clearly fall back to lexical search. In Ollama mode no key is required, but a running server and downloaded models are required; requests surface server/model errors. Production AI results are never simulated. Live OpenAI and Crossref calls require credentials/network and are not established by mocked integration tests. AI interpretations can be wrong even when quote verification succeeds.

## Storage, deletion and backup

`data/researchvault.sqlite3` stores metadata, extracted chunks, FTS index, profile and evidence. `data/uploads/<paper_id>.pdf` holds originals. `data/chroma/` holds persistent vectors. `.env`, `.venv`, local data, caches and logs are ignored by Git.

Stop Streamlit and copy the **entire data directory** to secure backup storage. Keep `.env` separately in secure storage if needed. Restore the full directory together before restarting. SQLite, PDFs and vectors must correspond. Changing chunk settings only affects new documents, not existing evidence references. Do not delete files manually from the data directory.

Paper deletion requires a checkbox, removes vectors in every model collection, then cascades source/evidence database records and removes the PDF. If vector cleanup fails, deletion stops so it can be retried. This intentionally deletes saved evidence for that paper. Back up first if you need to retain it.

The app is for a trusted single local user. It has no authentication or multi-user isolation. Bind to loopback by default; do not publish the Streamlit port directly. Uploaded PDFs are parsed, never executed as code. Keep dependencies current; file validation is not a malware scanner.

## Validation and development

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q app.py core services tests
.\.venv\Scripts\python.exe -m pip check
```

Tests create synthetic PDFs in temporary directories, clearly marked as test fixtures. They never populate your real literature library. They exercise upload validation, multiple documents, deduplication, persistence, profile edits, synonym-expanded keyword retrieval, page-accurate quotes, fabricated-quote rejection, evidence editing, Excel output, DOI uniqueness, deletion, missing-key behavior, AI output validation, vector persistence/cache and all eight Streamlit pages. Vector/AI tests use deterministic test doubles, not fabricated production AI responses. Streamlit AppTest validates rendered application behavior; it does not verify native browser PDF rendering.

See `NEXT_STEPS.md` for remaining verification and enhancements. The project uses existing isolated checkouts; no additional Git worktree is needed.

Ollama provider protocol, invalid/truncated responses, embedding validation, provider-separated collections, connection errors and key-free UI configuration have additional automated tests. These use controlled responses; they do not establish live Llama quality or GPU behavior.
