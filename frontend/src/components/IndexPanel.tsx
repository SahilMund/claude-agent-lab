import { useEffect, useState } from "react";
import { getIndexStatus, reindex, type IndexStatus } from "../api";

export function IndexPanel() {
  const [status, setStatus] = useState<IndexStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setError(null);
    try {
      setStatus(await getIndexStatus());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleReindex = async () => {
    setLoading(true);
    setError(null);
    try {
      setStatus(await reindex());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="panel">
      <h2>Index status</h2>
      <p className="panel-hint">
        The API indexes the repo it was started in on startup. Re-index after editing files —
        the file watcher that would normally do this automatically is a known gap with the
        Qdrant backend (see docs/progress.md).
      </p>

      {error && <div className="error-box">{error}</div>}

      {status ? (
        <dl className="stat-grid">
          <dt>Repo path</dt>
          <dd className="mono">{status.repo_path}</dd>
          <dt>Collection</dt>
          <dd className="mono">{status.collection_name}</dd>
          <dt>Chunks indexed</dt>
          <dd className="stat-number">{status.chunks_indexed}</dd>
        </dl>
      ) : (
        !error && <p>Loading…</p>
      )}

      <button onClick={handleReindex} disabled={loading}>
        {loading ? "Re-indexing…" : "Re-index now"}
      </button>
    </section>
  );
}
