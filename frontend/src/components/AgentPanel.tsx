import { useRef, useState, type FormEvent } from "react";
import { streamAgent, type AgentStreamEvent } from "../api";

type TraceEntry =
  | { kind: "tool_start"; tool: string; input: unknown }
  | { kind: "tool_end"; tool: string; output: string }
  | { kind: "final"; answer: string }
  | { kind: "error"; error: string };

export function AgentPanel() {
  const [question, setQuestion] = useState("");
  const [trace, setTrace] = useState<TraceEntry[]>([]);
  const [running, setRunning] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!question.trim() || running) return;

    setTrace([]);
    setRunning(true);
    const controller = new AbortController();
    abortRef.current = controller;

    const onEvent = (streamEvent: AgentStreamEvent) => {
      setTrace((previous) => [...previous, streamEventToEntry(streamEvent)]);
    };

    try {
      await streamAgent(question, onEvent, undefined, controller.signal);
    } catch (err) {
      if (!controller.signal.aborted) {
        setTrace((previous) => [
          ...previous,
          { kind: "error", error: err instanceof Error ? err.message : String(err) },
        ]);
      }
    } finally {
      setRunning(false);
    }
  };

  const handleStop = () => {
    abortRef.current?.abort();
    setRunning(false);
  };

  return (
    <section className="panel">
      <h2>Watch the agent work</h2>
      <p className="panel-hint">
        Same question the agent would answer for /ask — this view streams every tool call as it
        happens instead of only showing the final answer.
      </p>

      <form onSubmit={handleSubmit} className="ask-form">
        <input
          type="text"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="What does read_file do and where is it defined?"
          disabled={running}
        />
        {running ? (
          <button type="button" onClick={handleStop}>
            Stop
          </button>
        ) : (
          <button type="submit" disabled={!question.trim()}>
            Run
          </button>
        )}
      </form>

      <ol className="trace-list">
        {trace.map((entry, index) => (
          <li key={index} className={`trace-entry trace-${entry.kind}`}>
            <TraceEntryView entry={entry} />
          </li>
        ))}
        {running && <li className="trace-entry trace-pending">…</li>}
      </ol>
    </section>
  );
}

function streamEventToEntry(event: AgentStreamEvent): TraceEntry {
  switch (event.type) {
    case "tool_start":
      return { kind: "tool_start", tool: event.tool, input: event.input };
    case "tool_end":
      return { kind: "tool_end", tool: event.tool, output: event.output };
    case "final":
      return { kind: "final", answer: event.answer };
    case "error":
      return { kind: "error", error: event.error };
  }
}

function TraceEntryView({ entry }: { entry: TraceEntry }) {
  switch (entry.kind) {
    case "tool_start":
      return (
        <>
          <span className="trace-label">→ calling</span>{" "}
          <span className="mono">{entry.tool}</span>
          <pre className="trace-detail">{JSON.stringify(entry.input, null, 2)}</pre>
        </>
      );
    case "tool_end":
      return (
        <>
          <span className="trace-label">← result from</span>{" "}
          <span className="mono">{entry.tool}</span>
          <pre className="trace-detail">{truncate(entry.output, 500)}</pre>
        </>
      );
    case "final":
      return (
        <>
          <span className="trace-label">✓ final answer</span>
          <div className="answer-box">{entry.answer}</div>
        </>
      );
    case "error":
      return <div className="error-box">{entry.error}</div>;
  }
}

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max)}…` : text;
}
