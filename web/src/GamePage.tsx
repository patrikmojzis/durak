import { Check, Copy, Eye, Image, ListChecks, Send, Shield, Skull, Swords, Terminal, Text } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { agentPacket, loadAgentConfigs, waitUrlWithSince } from "./agentConfig";
import { copyText, getGame, sendAction, waitGame } from "./api";
import { CardView, Table, suitSymbol } from "./Board";
import type { AgentConfig, DefendAction, GameAction, GameState, Player } from "./types";

function tokenFromUrl(): string {
  return new URLSearchParams(window.location.search).get("token") || "";
}

function endpointWithToken(gameId: string, path: string, token: string, params: Record<string, string | number> = {}) {
  const base = path ? `/api/games/${gameId}/${path}` : `/api/games/${gameId}`;
  const search = new URLSearchParams({ token });
  Object.entries(params).forEach(([key, value]) => search.set(key, String(value)));
  return `${base}?${search.toString()}`;
}

function absoluteUrl(path: string) {
  return `${window.location.origin}${path}`;
}

function statusText(state: GameState) {
  if (state.result === "no_durak") return "No durak";
  if (state.durak) return `${state.durak.toUpperCase()} is durak`;
  if (state.canAct) return "Your move";
  if (state.currentActors.length) return `${state.currentActors.map((p) => p.toUpperCase()).join(", ")} can act`;
  return "Waiting";
}

function EndpointList({ config }: { config: AgentConfig }) {
  const endpoints = [
    ["stateUrl", "Partial JSON state.", config.stateUrl],
    ["legalActionsUrl", "Exact legal actions.", config.legalActionsUrl],
    ["waitUrl", "Long-poll with since=version.", waitUrlWithSince(config)],
    ["actionUrl", "POST one legal action.", config.actionUrl],
    ["boardTextUrl", "Readable text state.", config.boardTextUrl],
    ["boardImageUrl", "PNG table view.", config.boardImageUrl]
  ];
  return (
    <div className="endpoint-list">
      {endpoints.map(([name, description, value]) => (
        <div key={name}>
          <strong>{name}</strong>
          <span>{description}</span>
          <code>{value}</code>
        </div>
      ))}
    </div>
  );
}

function ActionButton({ action, onClick }: { action: GameAction; onClick: (action: GameAction) => void }) {
  let label: string = action.type;
  let icon = <Swords size={16} />;
  if (action.type === "attack") label = `Attack ${action.card}`;
  if (action.type === "throw_in") label = `Throw ${action.card}`;
  if (action.type === "defend") label = `Defend #${action.attackId} with ${action.card}`;
  if (action.type === "pass") {
    label = "Pass";
    icon = <Shield size={16} />;
  }
  if (action.type === "take") {
    label = "Take";
    icon = <Skull size={16} />;
  }
  if (action.type === "ready") {
    label = "Done";
    icon = <Check size={16} />;
  }
  return (
    <button onClick={() => onClick(action)}>
      {icon}
      {label}
    </button>
  );
}

function Hand({ state, onAction }: { state: GameState; onAction: (action: GameAction) => void }) {
  const cardActions = new Map<string, GameAction[]>();
  for (const action of state.legalActions) {
    if ("card" in action && action.card) {
      const list = cardActions.get(action.card) || [];
      list.push(action);
      cardActions.set(action.card, list);
    }
  }

  return (
    <section className="hand-panel">
      <div className="panel-head">
        <div>
          <span className="field-label">Hand</span>
          <h2>{state.viewer === "spectator" ? "Spectator" : state.viewer.toUpperCase()}</h2>
        </div>
        <strong>{state.hand.length} cards</strong>
      </div>
      <div className="hand-row">
        {state.hand.length ? (
          state.hand.map((card) => {
            const legal = cardActions.get(card) || [];
            return (
              <div className="hand-card" key={card}>
                <CardView card={card} />
                {legal.map((action, index) => (
                  <button key={`${card}-${action.type}-${index}`} disabled={!state.canAct} onClick={() => onAction(action)}>
                    {action.type === "defend" ? `#${(action as DefendAction).attackId}` : action.type === "throw_in" ? "throw" : "play"}
                  </button>
                ))}
              </div>
            );
          })
        ) : (
          <p className="quiet-line">{state.viewer === "spectator" ? "Spectators cannot see private hands." : "No cards."}</p>
        )}
      </div>
    </section>
  );
}

function PlayControls({
  state,
  note,
  busy,
  error,
  onNote,
  onAction
}: {
  state: GameState;
  note: string;
  busy: boolean;
  error: string | null;
  onNote: (value: string) => void;
  onAction: (action: GameAction) => void;
}) {
  const nonCardActions = state.legalActions.filter((action) => !("card" in action));
  if (state.viewer === "spectator") {
    return null;
  }

  const hasCardActions = state.legalActions.some((action) => "card" in action);
  return (
    <section className={`play-controls ${state.canAct ? "is-active" : ""}`}>
      <div className="play-controls-head">
        <div>
          <span className="field-label">Play</span>
          <strong>{state.canAct ? "Your available moves" : "Waiting for another seat"}</strong>
        </div>
        {busy && <span className="busy-pill">Submitting</span>}
      </div>
      {nonCardActions.length > 0 && (
        <div className="action-grid primary-actions">
          {nonCardActions.map((action) => (
            <ActionButton key={action.type} action={action} onClick={onAction} />
          ))}
        </div>
      )}
      {state.canAct && hasCardActions && <p className="quiet-line">Tap a highlighted action below a card in your hand.</p>}
      {!state.legalActions.length && <p className="quiet-line">No legal action right now.</p>}
      {error && <p className="error-text">{error}</p>}
      <details className="note-details">
        <summary>Private note</summary>
        <textarea
          value={note}
          onChange={(event) => onNote(event.target.value)}
          maxLength={500}
          placeholder="Optional note, revealed after game"
        />
      </details>
    </section>
  );
}

export function GamePage({ gameId }: { gameId: string }) {
  const token = useMemo(tokenFromUrl, []);
  const [state, setState] = useState<GameState | null>(null);
  const [storedConfigs] = useState(() => loadAgentConfigs(gameId));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const versionRef = useRef(-1);

  function remember(next: GameState) {
    versionRef.current = next.version;
    setState(next);
  }

  useEffect(() => {
    let cancelled = false;
    async function run() {
      if (!token) {
        setError("Missing token in URL");
        return;
      }
      try {
        const initial = await getGame(gameId, token);
        if (cancelled) return;
        remember(initial);
        while (!cancelled) {
          const next = await waitGame(gameId, token, versionRef.current);
          if (!cancelled) remember(next);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load game");
      }
    }
    run();
    return () => {
      cancelled = true;
    };
  }, [gameId, token]);

  async function act(action: GameAction) {
    if (!token || !state?.canAct) return;
    setBusy(true);
    setError(null);
    try {
      const withNote = note.trim() ? ({ ...action, note: note.trim() } as GameAction) : action;
      remember(await sendAction(gameId, token, withNote));
      setNote("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy(false);
    }
  }

  async function copy(label: string, value: string) {
    await copyText(value);
    setCopied(label);
  }

  if (error && !state) {
    return (
      <main className="game-shell centered">
        <section className="empty-state">
          <h1>Durak</h1>
          <p>{error}</p>
          <a href="/">Create a fresh table</a>
        </section>
      </main>
    );
  }

  if (!state) {
    return (
      <main className="game-shell centered">
        <section className="empty-state">
          <h1>Durak</h1>
          <p>Loading table...</p>
        </section>
      </main>
    );
  }

  const stateUrl = endpointWithToken(gameId, "", token);
  const legalActionsUrl = endpointWithToken(gameId, "legal-actions", token);
  const boardTextUrl = endpointWithToken(gameId, "board.txt", token);
  const boardImageUrl = endpointWithToken(gameId, "board.png", token, { v: state.version });
  const waitUrl = endpointWithToken(gameId, "wait", token, { since: state.version });
  const actionUrl = endpointWithToken(gameId, "actions", token);
  const isSpectator = state.viewer === "spectator";
  const storedSeats = state.players.map((player) => storedConfigs[player]).filter((config): config is AgentConfig => Boolean(config));

  return (
    <main className="game-shell">
      <header className="game-topbar">
        <a className="brand-link" href="/">
          <span className="brand-mark small">{suitSymbol(state.trumpSuit)}</span>
          <span>Durak</span>
        </a>
        <div className={`turn-pill ${state.canAct ? "is-yours" : ""}`}>
          {state.result ? <Skull size={17} /> : <Swords size={17} />}
          {statusText(state)}
        </div>
      </header>

      <section className="game-layout">
        <div className="board-stage">
          <Table state={state} />
          <Hand state={state} onAction={act} />
          <PlayControls state={state} note={note} busy={busy} error={error} onNote={setNote} onAction={act} />
        </div>

        <aside className="side-panel">
          <div className="player-strip">
            {state.players.map((player) => {
              const info = state.playerInfo[player];
              return (
                <div key={player} className={`player-chip ${state.currentActors.includes(player) ? "active" : ""} ${info.finished ? "finished" : ""}`}>
                  <span className="mini-card">{info.cardCount}</span>
                  <div>
                    <strong>{info.name}</strong>
                    <span>
                      {player.toUpperCase()} · {info.human ? "human" : "agent"}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          {isSpectator && (
            <div className="control-block">
              <span className="field-label">Spectator</span>
              <p className="quiet-copy">This token cannot act and cannot see private hands.</p>
            </div>
          )}

          {state.cramped && (
            <div className="control-block warning-block">
              <span className="field-label">Cramped table</span>
              <p>36-card, 6-player setup: everyone got six cards, so there is no draw pile.</p>
            </div>
          )}

          {storedSeats.length > 0 && (
            <details className="collapsible-card agent-handoff" open>
              <summary>
                <span>
                  <Send size={17} />
                  Agent seats
                </span>
                <small>{storedSeats.map((seat) => seat.player.toUpperCase()).join(" + ")}</small>
              </summary>
              <div className="agent-packet-actions">
                {storedSeats.map((config) => (
                  <button key={config.player} onClick={() => copy(`${config.player.toUpperCase()} packet`, agentPacket(config))}>
                    <Copy size={17} />
                    Copy {config.player.toUpperCase()}
                  </button>
                ))}
              </div>
              {storedSeats.map((config) => (
                <details className="nested-details" key={config.player}>
                  <summary>{config.player.toUpperCase()} endpoints</summary>
                  <EndpointList config={config} />
                </details>
              ))}
            </details>
          )}

          {copied && (
            <p className="copied-text copied-inline">
              <Check size={15} /> Copied {copied}
            </p>
          )}

          <details className="collapsible-card">
            <summary>
              <span>
                <Terminal size={17} />
                Current token tools
              </span>
              <small>{state.viewer}</small>
            </summary>
            <div className="copy-grid">
              <button onClick={() => copy("state URL", absoluteUrl(stateUrl))}>
                <ListChecks size={16} />
                state
              </button>
              <button onClick={() => copy("legal actions", absoluteUrl(legalActionsUrl))}>
                <Shield size={16} />
                legal
              </button>
              <button onClick={() => copy("wait URL", absoluteUrl(waitUrl))}>
                <Eye size={16} />
                wait
              </button>
              <button onClick={() => copy("action URL", absoluteUrl(actionUrl))}>
                <Swords size={16} />
                action
              </button>
              <button onClick={() => copy("state JSON", JSON.stringify(state, null, 2))}>
                <Copy size={16} />
                JSON
              </button>
            </div>
          </details>

          <details className="collapsible-card">
            <summary>
              <span>
                <Image size={17} />
                Agent views
              </span>
              <small>text + PNG</small>
            </summary>
            <div className="copy-grid">
              <button onClick={() => copy("board.txt", absoluteUrl(boardTextUrl))}>
                <Text size={16} />
                text
              </button>
              <button onClick={() => copy("board.png", absoluteUrl(boardImageUrl))}>
                <Image size={16} />
                image
              </button>
            </div>
            <div className="board-preview">
              <img src={boardImageUrl} alt="Current Durak table rendered for agents" />
            </div>
          </details>

          <details className="collapsible-card history-block">
            <summary>
              <span>Recent log</span>
              <small>v{state.version}</small>
            </summary>
            {state.history.length === 0 ? (
              <p className="quiet-line">Nothing yet.</p>
            ) : (
              <ol>
                {state.history.slice(-10).map((item, index) => (
                  <li key={`${index}-${JSON.stringify(item)}`}>
                    <strong>v{String(item.version ?? "?")}</strong> {String(item.type)}
                    {item.card ? ` ${String(item.card)}` : ""}
                    {item.player ? ` by ${String(item.player).toUpperCase()}` : ""}
                    {item.attacker ? ` attacker ${String(item.attacker).toUpperCase()}` : ""}
                    {item.defender ? ` defender ${String(item.defender).toUpperCase()}` : ""}
                  </li>
                ))}
              </ol>
            )}
          </details>

          {state.replay && (
            <details className="collapsible-card history-block">
              <summary>
                <span>Full replay</span>
                <small>revealed</small>
              </summary>
              <pre className="config-preview">{JSON.stringify({ initialHands: state.initialHands, finalHands: state.finalHands, replay: state.replay }, null, 2)}</pre>
            </details>
          )}
        </aside>
      </section>
    </main>
  );
}
