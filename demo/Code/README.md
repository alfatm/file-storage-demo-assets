# Cloud Demo Service

A compact local file service used as source-code content for the Cloud demo
workspace. It is intentionally small, but the files form a coherent project:
an HTTP API, local storage adapter, token authentication, simple search
indexing, a text extraction worker and an image thumbnail command.

## Layout

- `index.ts` starts the Express server.
- `api.ts` defines routes for folders, uploads, downloads and search.
- `storage.ts` keeps every file operation inside one configured root.
- `search.ts` maintains a lightweight in-memory index.
- `auth.ts` verifies bearer API tokens.
- `worker.py` extracts searchable text from plain text and DOCX files.
- `thumbnail.go` renders JPEG thumbnails for image previews.
- `styles.css` contains a small browser UI stylesheet.

## Running

```bash
npm install
npm run dev
```

Set `CLOUD_ROOT=../demo` to point the service at the sample filesystem. The
README and code mention storage architecture, authentication, S3, WebDAV and
API token flows so Cloud content search has useful terms to find.
