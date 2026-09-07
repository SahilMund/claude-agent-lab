import { useState, type FormEvent } from "react";
import { ask, type AskResponse } from "../api";

export function AskPanel() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<AskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!question.trim() || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await ask(question));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="panel">
      <h2>Ask the codebase</h2>
      <p className="panel-hint">
        One question, one grounded answer — retrieval happens once, then the agent answers.
        Sources are fetched independently of the agent's own tool call, so they show up even
        if the model call itself fails.
      </p>

      <form onSubmit={handleSubmit} className="ask-form">
        <input
          type="text"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="How does the config system decide precedence?"
          disabled={loading}
        />
        <button type="submit" disabled={loading || !question.trim()}>
          {loading ? "Asking…" : "Ask"}
        </button>
      </form>

      {error && <div className="error-box">{error}</div>}

      {result && (
        <div className="ask-result">
          <div className="answer-box">{result.answer}</div>

          {result.sources.length > 0 && (
            <>
              <h3>Sources</h3>
              <ul className="source-list">
                {result.sources.map((source, index) => (
                  <li key={index} className="source-item">
                    <span className="source-kind">{source.type}</span>
                    <span className="source-name mono">{source.name}</span>
                    <span className="source-location mono">
                      {source.source}:{source.start_line}-{source.end_line}
                    </span>
                    {source.distance !== null && (
                      <span className="source-score">score {source.distance.toFixed(3)}</span>
                    )}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </section>
  );
}
