# claude_agent_lab dashboard

React + Vite frontend for the Phase 8 dashboard — a second way to see the CLI's backend
(`claude_agent_lab/api/`), not a replacement for it.

## Run

```bash
npm install
npm run dev
```

Needs the backend running first (from the repo root):

```bash
uvicorn claude_agent_lab.api.app:app --port 8000
```

Defaults to `http://localhost:8000` for the API — override with `VITE_API_BASE_URL` in
`.env.local` (see `.env.example`) if you run the backend on a different port.

## Views

- **Index** — current index size, a button to trigger a full re-index.
- **Ask** — one question, one grounded answer, plus the retrieved sources it's grounded in.
- **Agent** — the same underlying question-answering, but streamed live: watch each tool call
  the agent makes (via Server-Sent Events) before the final answer arrives.
