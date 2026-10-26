# Outstanding work

## Before relying on AI results in a real review
- Supply an OpenAI API key privately and exercise actual embedding, relevance, passage classification and synthesis calls. Verify model availability, costs, structured-output compatibility and the quality of real responses. These paths are implemented but live-provider behavior is not validated here.
- Run Crossref lookup against a DOI from your own uploaded paper and confirm document/metadata correspondence. Automatic DOI extraction/inference is pending.
- Manually validate native browser PDF display at the selected page; Streamlit AppTest cannot exercise the browser's PDF plugin. Download fallback is present.
- Validate installation and start.bat on actual Windows/Python 3.11+; current execution environment is Linux/Python 3.12.

## Known MVP limits
- Search modes share the retrieval interface. Conceptual search needs semantic indexing; cross-paper synthesis deliberately uses selected saved evidence in the dedicated page.
- Construct selection is query context/synonym expansion, not a strict validated classification filter. Manual evidence classifications are supported.
- Partial/scanned pages are flagged for OCR review; there is no OCR. Very short legitimate text pages may also be flagged.
- Metadata comes from PDF properties, manual input, or user-provided DOI lookup. No automatic author/title inference or DOI extraction.
- Printed page numbering and section detection are not implemented; physical PDF page references are preserved.
- Synthesis schema and reference IDs are validated, but unsupported prose claims cannot be automatically excluded with certainty. Researcher verification remains required.
- Long documents are sampled for relevance. Search uses bounded candidate pools; neither is exhaustive.
- No advanced learned reranker, precise quote highlighting, granular embedding progress UI, fully locked transitive dependency graph, or automatic stale-assessment recomputation.
- Bulk operations are sequential with per-document error recovery, suitable for local use rather than a background job queue.

## Future phases
OCR; Zotero; multi-profile switching; multi-user authentication; exact PDF highlighting; research-gap mapping; Word export; advanced citation styles; production cloud deployment. Do not treat these as delivered features.
