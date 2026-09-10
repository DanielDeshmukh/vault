# Phase 2 — Ingestion Pipeline

**Duration:** Days 4–7  
**Goal:** Ingest documents from 7 sources, chunk, tag metadata, store in Pinecone

---

## Day 4 — Connector Framework + Zendesk/Jira

### Base Connector

- [ ] Create abstract `BaseConnector` class
  ```python
  class BaseConnector(ABC):
      @abstractmethod
      async def fetch(self, config: dict) -> AsyncIterator[RawDocument]: ...
      @abstractmethod
      def extract_metadata(self, doc: RawDocument) -> DocumentMetadata: ...
  ```

### Zendesk Connector

- [ ] Connect to Zendesk API (tickets + comments)
- [ ] Map `org_id` → `account_id`
- [ ] Set `department = "support"`
- [ ] Handle pagination, rate limiting
- [ ] Extract attachments (PDF, images)

### Jira Connector

- [ ] Connect to Jira API (issues + comments)
- [ ] Map `project.key` → `account_id`
- [ ] Set `department = "engineering"`
- [ ] Handle pagination
- [ ] Link related issues

---

## Day 5 — Slack + Confluence

### Slack Connector

- [ ] Accept Slack export (JSON format)
- [ ] Parse channels, threads, reactions
- [ ] Map workspace → `account_id`
- [ ] Derive department from channel name
- [ ] Handle file attachments

### Confluence Connector

- [ ] Connect to Confluence API (pages + spaces)
- [ ] Map `space.key` → `account_id`
- [ ] Parse HTML content to text
- [ ] Handle nested pages
- [ ] Extract embedded links

---

## Day 6 — Transcripts + Policies + CSV

### Transcript Connector

- [ ] Parse call recording transcripts (text format)
- [ ] Extract customer_id from metadata
- [ ] Set `department = "support"` or `"sales"`
- [ ] Handle speaker diarization
- [ ] Timestamp extraction

### Policy Connector

- [ ] Accept PDF/DOCX policy files
- [ ] Set `account_id = "internal"`
- [ ] Derive department from filename/path
- [ ] Handle multi-page documents

### CSV Uploader

- [ ] Accept CSV file upload
- [ ] Column mapping UI/config
- [ ] Row-level metadata extraction
- [ ] Bulk insert support

---

## Day 7 — Parsers + Chunker + Pinecone

### Parsers

- [ ] PDF parser (pypdf)
- [ ] DOCX parser (python-docx)
- [ ] HTML parser (beautifulsoup4)
- [ ] Plain text parser
- [ ] Parser router (auto-detect format)

### Semantic Chunker

- [ ] Fixed-size chunking (512 tokens default)
- [ ] Overlap (128 tokens default)
- [ ] Respect document boundaries
- [ ] Preserve metadata per chunk

### Pinecone Integration

- [ ] Initialize Pinecone client
- [ ] Create index with dimension (nomic-embed-text = 768)
- [ ] Upsert vectors with metadata
- [ ] Metadata schema enforcement

---

## Exit Criteria

- [ ] Can ingest from all 7 sources
- [ ] Documents are chunked correctly
- [ ] Metadata is extracted and stored
- [ ] Vectors are in Pinecone with metadata
- [ ] Test ingestion via API endpoint

---

## Files Created

```
backend/app/ingestion/
├── __init__.py
├── pipeline.py
├── connectors/
│   ├── __init__.py
│   ├── base.py
│   ├── zendesk.py
│   ├── jira.py
│   ├── slack.py
│   ├── confluence.py
│   ├── transcripts.py
│   ├── policies.py
│   └── csv_uploader.py
├── parsers/
│   ├── __init__.py
│   ├── pdf.py
│   ├── docx.py
│   ├── html.py
│   └── text.py
├── chunker.py
└── metadata.py
```
