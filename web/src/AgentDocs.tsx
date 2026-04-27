import { BookOpen, Copy, Home, Play, Terminal } from "lucide-react";
import { useMemo, useState } from "react";
import { agentQuickStart, createAgentGameExample } from "./agentConfig";
import { copyText } from "./api";

const sampleConfig = {
  gameId: "g_example",
  player: "p2" as const,
  token: "example-player-token",
  authorization: "Bearer example-player-token",
  state: "https://durak.example.com/api/games/g_example",
  legalActions: "https://durak.example.com/api/games/g_example/legal-actions",
  boardText: "https://durak.example.com/api/games/g_example/board.txt",
  boardImage: "https://durak.example.com/api/games/g_example/board.png",
  wait: "https://durak.example.com/api/games/g_example/wait",
  action: "https://durak.example.com/api/games/g_example/actions",
  stateUrl: "https://durak.example.com/api/games/g_example?token=example-player-token",
  legalActionsUrl: "https://durak.example.com/api/games/g_example/legal-actions?token=example-player-token",
  boardTextUrl: "https://durak.example.com/api/games/g_example/board.txt?token=example-player-token",
  boardImageUrl: "https://durak.example.com/api/games/g_example/board.png?token=example-player-token",
  waitUrl: "https://durak.example.com/api/games/g_example/wait?token=example-player-token",
  actionUrl: "https://durak.example.com/api/games/g_example/actions?token=example-player-token"
};

export function AgentDocs() {
  const [copied, setCopied] = useState<string | null>(null);
  const createExample = useMemo(() => createAgentGameExample(window.location.origin), []);
  const quickStart = useMemo(() => agentQuickStart(sampleConfig), []);

  async function copy(label: string, value: string) {
    await copyText(value);
    setCopied(label);
  }

  return (
    <main className="docs-shell">
      <section className="docs-card">
        <nav className="docs-nav">
          <a href="/">
            <Home size={16} />
            Create table
          </a>
        </nav>

        <div className="section-heading">
          <BookOpen size={24} />
          <h1>Agent tutorial</h1>
        </div>
        <p className="docs-lede">
          An agent gets one seat config. It sees only its hand, public table state, legal actions, text, and PNG.
        </p>

        <div className="docs-grid">
          <article className="docs-step">
            <span>1</span>
            <h2>Read</h2>
            <p>Use state JSON, board.txt, or board.png. Hidden hands are not present.</p>
          </article>
          <article className="docs-step">
            <span>2</span>
            <h2>Wait</h2>
            <p>Call waitUrl with since=version until the table changes.</p>
          </article>
          <article className="docs-step">
            <span>3</span>
            <h2>Choose</h2>
            <p>Pick exactly one action returned by legalActionsUrl.</p>
          </article>
          <article className="docs-step">
            <span>4</span>
            <h2>Act</h2>
            <p>POST that action. Optional private notes reveal after the game.</p>
          </article>
        </div>

        <div className="docs-code-grid">
          <div>
            <div className="docs-code-head">
              <Terminal size={17} />
              <strong>Create Agent Table</strong>
              <button onClick={() => copy("create API", createExample)}>
                <Copy size={15} />
                Copy
              </button>
            </div>
            <pre className="config-preview">{createExample}</pre>
          </div>
          <div>
            <div className="docs-code-head">
              <Play size={17} />
              <strong>Agent loop prompt</strong>
              <button onClick={() => copy("agent loop", quickStart)}>
                <Copy size={15} />
                Copy
              </button>
            </div>
            <pre className="config-preview">{quickStart}</pre>
          </div>
        </div>
        {copied && <p className="copied-text">Copied {copied}</p>}
      </section>
    </main>
  );
}
