// Thin client for the FastAPI backend (claude_agent_lab/api/). One function
// per endpoint — no state, no caching here; the components own their state.

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export interface IndexStatus {
  repo_path: string;
  collection_name: string;
  chunks_indexed: number;
}

export interface SourceChunk {
  source: string;
  name: string;
  type: string;
  start_line: number;
  end_line: number;
  distance: number | null;
}

export interface AskResponse {
  answer: string;
  thread_id: string;
  sources: SourceChunk[];
}

async function asJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${body}`);
  }
  return response.json() as Promise<T>;
}

export async function getIndexStatus(): Promise<IndexStatus> {
  return asJson(await fetch(`${API_BASE}/index/status`));
}

export async function reindex(): Promise<IndexStatus> {
  return asJson(await fetch(`${API_BASE}/index`, { method: "POST" }));
}

export async function ask(question: string, threadId?: string): Promise<AskResponse> {
  return asJson(
    await fetch(`${API_BASE}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, thread_id: threadId ?? null }),
    })
  );
}

// --- Agent trace streaming ---------------------------------------------
//
// The backend streams Server-Sent Events over a POST response (sse-starlette).
// The browser's built-in EventSource can't send a POST body, so this parses
// the SSE wire format ("event: ...\ndata: ...\n\n") by hand from a fetch()
// response's streamed body instead.

export type AgentStreamEvent =
  | { type: "tool_start"; tool: string; input: unknown }
  | { type: "tool_end"; tool: string; output: string }
  | { type: "final"; answer: string }
  | { type: "error"; error: string };

export async function streamAgent(
  question: string,
  onEvent: (event: AgentStreamEvent) => void,
  threadId?: string,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(`${API_BASE}/agent/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, thread_id: threadId ?? null }),
    signal,
  });
  if (!response.ok || !response.body) {
    throw new Error(`${response.status} ${response.statusText}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE messages are separated by a blank line.
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const raw = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");

      const eventLine = raw.split("\n").find((line) => line.startsWith("event:"));
      const dataLine = raw.split("\n").find((line) => line.startsWith("data:"));
      if (!eventLine || !dataLine) continue;

      const kind = eventLine.slice("event:".length).trim();
      const data = JSON.parse(dataLine.slice("data:".length).trim());
      onEvent({ type: kind, ...data } as AgentStreamEvent);
    }
  }
}
