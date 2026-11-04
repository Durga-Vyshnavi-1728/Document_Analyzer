# Document Analyzer

A lightweight Streamlit app for asking natural-language questions about multiple documents.

## Supported formats
- PDF (`.pdf`)
- Word (`.docx`)
- Excel (`.xlsx`, `.xls`)
- PowerPoint (`.pptx`)
- Plain text (`.txt`)
- Markdown (`.md`)

Legacy binary Word `.doc` files are not supported directly; open them in Word and save as `.docx`.

## Features
- Upload multiple supported documents in one session and ask questions across them.
- Extracts text locally and keeps source names plus page, slide, sheet or document locations.
- Uses Gemini embeddings (`gemini-embedding-001`) for semantic retrieval when available.
- Combines semantic similarity with BM25-style keyword ranking.
- Falls back to keyword retrieval if embedding requests are unavailable.
- Sends selected passages and recent chat context to Gemini for grounded answers.
- Shows source file and location references alongside answers.
- Converts common transient 503/504 errors into readable messages.

## Windows setup
1. Extract the project folder.
2. Run `setup_windows.bat`.
3. Copy `.env.example` to `.env` if it does not already exist, then add your Gemini API key.
4. Keep `GEMINI_MODEL=gemini-3-flash-preview` unless you select another model ID supported by `generateContent` for your API key.
5. Run `run.bat`.

Or from CMD:
```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Notes and limitations
- PDF scanned images need OCR; OCR is not included.
- DOCX page boundaries are not reliably stored in the file, so sources are cited by document rather than page.
- Excel sources are cited by worksheet; PowerPoint sources by slide.
- Semantic search uses Gemini's embedding API and consumes API quota. If it is unavailable, keyword retrieval remains available.
- For important legal, insurance or financial decisions, verify answers against the original files.
