import { Bot, Copy, Eye, ExternalLink, Play, Shuffle, Spade, UserRound, UsersRound } from "lucide-react";
import { useMemo, useState } from "react";
import { agentPacket, allAgentConfigsJson, createAgentGameExample, saveAgentConfigs } from "./agentConfig";
import { copyText, createGame, toLocalGameUrl } from "./api";
import type { AgentConfig, CreateGameResponse, DeckType, FirstAttacker, Player } from "./types";

function seatList(count: number): Player[] {
  return Array.from({ length: count }, (_, index) => `p${index + 1}` as Player);
}

function AgentInviteCard({ config, onCopy }: { config: AgentConfig; onCopy: (label: string, text: string) => Promise<void> }) {
  return (
    <article className="invite-card">
      <div>
        <span className="field-label">Agent seat</span>
        <h3>{config.player.toUpperCase()}</h3>
        <p>Private token. Send only to the agent playing this seat.</p>
      </div>
      <button onClick={() => onCopy(`${config.player.toUpperCase()} packet`, agentPacket(config))}>
        <Copy size={16} />
        Copy packet
      </button>
    </article>
  );
}

export function CreateGame() {
  const [playerCount, setPlayerCount] = useState(4);
  const [deckType, setDeckType] = useState<DeckType>("36");
  const [firstAttacker, setFirstAttacker] = useState<FirstAttacker>("lowest-trump");
  const [humanSeats, setHumanSeats] = useState<Player[]>(["p1"]);
  const [names, setNames] = useState<Record<Player, string>>({ p1: "Patrik" });
  const [result, setResult] = useState<CreateGameResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  const seats = useMemo(() => seatList(playerCount), [playerCount]);

  function toggleHuman(seat: Player) {
    setHumanSeats((current) => (current.includes(seat) ? current.filter((item) => item !== seat) : [...current, seat]));
  }

  async function submit() {
    setBusy(true);
    setError(null);
    setCopied(null);
    try {
      const created = await createGame({
        playerCount,
        deckType,
        firstAttacker,
        humanSeats: humanSeats.filter((seat) => seats.includes(seat)),
        names
      });
      saveAgentConfigs(created.gameId, created.agentConfigs);
      setResult(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create game");
    } finally {
      setBusy(false);
    }
  }

  async function copy(label: string, text: string) {
    await copyText(text);
    setCopied(label);
  }

  return (
    <main className="create-shell">
      <section className="create-art-panel">
        <div className="brand-row">
          <div className="brand-mark">
            <Spade size={30} />
          </div>
          <div>
            <h1>Durak</h1>
            <p>Podkidnoy table for humans and API agents. No hidden-hand leaks. No mercy either.</p>
          </div>
        </div>
        <img className="create-art" src="/assets/durak-table.png" alt="" />
      </section>

      <section className="create-controls" aria-label="Create Durak game">
        <div className="section-heading">
          <UsersRound size={23} />
          <h2>Create table</h2>
        </div>

        <div className="field-group">
          <span className="field-label">Players</span>
          <div className="segmented count-grid">
            {[2, 3, 4, 5, 6].map((count) => (
              <button
                key={count}
                className={playerCount === count ? "active" : ""}
                onClick={() => {
                  setPlayerCount(count);
                  setHumanSeats((current) => current.filter((seat) => Number(seat.slice(1)) <= count));
                }}
              >
                {count}
              </button>
            ))}
          </div>
        </div>

        <div className="field-group two-col-fields">
          <div>
            <span className="field-label">Deck</span>
            <div className="segmented compact">
              <button className={deckType === "36" ? "active" : ""} onClick={() => setDeckType("36")}>
                36 cards
              </button>
              <button className={deckType === "52" ? "active" : ""} onClick={() => setDeckType("52")}>
                52 cards
              </button>
            </div>
            {playerCount === 6 && deckType === "36" && <p className="mode-note">Cramped table: everyone gets six cards, no draw pile.</p>}
          </div>
          <div>
            <span className="field-label">First attacker</span>
            <div className="segmented compact">
              <button className={firstAttacker === "lowest-trump" ? "active" : ""} onClick={() => setFirstAttacker("lowest-trump")}>
                <Spade size={15} />
                Lowest trump
              </button>
              <button className={firstAttacker === "random" ? "active" : ""} onClick={() => setFirstAttacker("random")}>
                <Shuffle size={15} />
                Random
              </button>
            </div>
          </div>
        </div>

        <div className="field-group">
          <span className="field-label">Seats</span>
          <div className="seat-editor">
            {seats.map((seat) => {
              const isHuman = humanSeats.includes(seat);
              return (
                <div className="seat-row" key={seat}>
                  <button className={`seat-kind ${isHuman ? "human" : ""}`} onClick={() => toggleHuman(seat)}>
                    {isHuman ? <UserRound size={16} /> : <Bot size={16} />}
                    {isHuman ? "Human" : "Agent"}
                  </button>
                  <strong>{seat.toUpperCase()}</strong>
                  <input
                    value={names[seat] || ""}
                    placeholder={isHuman ? "Human name" : `Agent ${seat.toUpperCase()}`}
                    onChange={(event) => setNames((current) => ({ ...current, [seat]: event.target.value }))}
                  />
                </div>
              );
            })}
          </div>
        </div>

        <button className="primary-action" disabled={busy} onClick={submit}>
          <Play size={19} />
          {busy ? "Creating..." : "Create table"}
        </button>
        {error && <p className="error-text">{error}</p>}

        {result && (
          <div className="result-panel">
            <div className="result-head">
              <div>
                <span className="field-label">Table ready</span>
                <strong>{result.gameId}</strong>
                <p>Copy private links carefully. A seat token is the seat.</p>
              </div>
              <button className="soft-button" onClick={() => (window.location.href = toLocalGameUrl(result.spectatorUrl))}>
                <Eye size={16} />
                Watch
              </button>
            </div>

            <div className="copy-row wrap">
              <button onClick={() => copy("spectator link", result.spectatorUrl)}>
                <Copy size={16} />
                Spectator
              </button>
              <button onClick={() => copy("all agent configs", allAgentConfigsJson(result.agentConfigs))}>
                <Copy size={16} />
                Agent configs
              </button>
              <button onClick={() => copy("create API", createAgentGameExample(window.location.origin))}>
                <Copy size={16} />
                Create API
              </button>
            </div>

            <div className="seat-link-grid">
              {result.players.map((seat) => (
                <article key={seat}>
                  <strong>{seat.toUpperCase()}</strong>
                  <span>{result.playerInfo[seat].name}</span>
                  <button onClick={() => copy(`${seat.toUpperCase()} link`, result.playerUrls[seat])}>
                    <Copy size={15} />
                    Copy link
                  </button>
                  <button onClick={() => (window.location.href = toLocalGameUrl(result.playerUrls[seat]))}>
                    <ExternalLink size={15} />
                    Open
                  </button>
                </article>
              ))}
            </div>

            {Object.values(result.agentConfigs).length > 0 && (
              <div className="agent-invite-grid">
                {Object.values(result.agentConfigs).map((config) => config && <AgentInviteCard key={config.player} config={config} onCopy={copy} />)}
              </div>
            )}
            {copied && <p className="copied-text">Copied {copied}</p>}
          </div>
        )}
      </section>
    </main>
  );
}
