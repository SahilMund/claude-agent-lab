import { useState } from "react";
import { IndexPanel } from "./components/IndexPanel";
import { AskPanel } from "./components/AskPanel";
import { AgentPanel } from "./components/AgentPanel";
import "./App.css";

type Tab = "index" | "ask" | "agent";

const TABS: { id: Tab; label: string }[] = [
  { id: "index", label: "Index" },
  { id: "ask", label: "Ask" },
  { id: "agent", label: "Agent" },
];

function App() {
  const [tab, setTab] = useState<Tab>("ask");

  return (
    <div className="app">
      <header className="app-header">
        <h1>claude_agent_lab</h1>
        <p>Dashboard over the CLI's backend — Phase 8</p>
      </header>

      <nav className="tabs">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            className={tab === id ? "tab active" : "tab"}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </nav>

      <main>
        {tab === "index" && <IndexPanel />}
        {tab === "ask" && <AskPanel />}
        {tab === "agent" && <AgentPanel />}
      </main>
    </div>
  );
}

export default App;
