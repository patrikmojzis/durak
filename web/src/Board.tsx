import type { CardInfo, GameState } from "./types";

const SUITS: Record<string, string> = {
  S: "♠",
  H: "♥",
  D: "♦",
  C: "♣"
};

const SUIT_NAMES: Record<string, string> = {
  S: "spades",
  H: "hearts",
  D: "diamonds",
  C: "clubs"
};

export function cardParts(code: string): CardInfo {
  return { rank: code.slice(0, -1), suit: code.slice(-1), code };
}

export function suitName(suit: string) {
  return SUIT_NAMES[suit] || suit;
}

export function suitSymbol(suit: string) {
  return SUITS[suit] || suit;
}

export function CardView({ card, small = false, muted = false }: { card: string | CardInfo | null; small?: boolean; muted?: boolean }) {
  if (!card) {
    return <div className={`card-view ${small ? "small" : ""} ${muted ? "waiting" : "back"}`} aria-label={muted ? "Waiting for defense card" : "Hidden card"} />;
  }
  const info = typeof card === "string" ? cardParts(card) : card;
  const red = info.suit === "H" || info.suit === "D";
  return (
    <div className={`card-view ${small ? "small" : ""} ${red ? "red" : ""} ${muted ? "muted" : ""}`} title={info.code}>
      <strong>{info.rank}</strong>
      <span>{suitSymbol(info.suit)}</span>
    </div>
  );
}

export function Table({ state }: { state: GameState }) {
  const bout = state.bout;
  return (
    <section className="table-surface" aria-label="Durak table">
      <div className="table-head">
        <div>
          <span className="field-label">Bout</span>
          {bout ? (
            <h2>
              {bout.attacker.toUpperCase()} attacks {bout.defender.toUpperCase()}
            </h2>
          ) : (
            <h2>{state.result === "no_durak" ? "No durak" : state.durak ? `${state.durak.toUpperCase()} is durak` : "Table settled"}</h2>
          )}
        </div>
        <div className="trump-box">
          <span>Trump</span>
          <strong>{suitSymbol(state.trumpSuit)}</strong>
          <small>{suitName(state.trumpSuit)}</small>
        </div>
      </div>

      <div className="pile-row">
        <div className="pile">
          <CardView card={state.stockCount ? null : state.trumpCard} small />
          <span>Draw {state.stockCount}</span>
        </div>
        <div className="pile">
          <div className="discard-stack">{state.discardCount}</div>
          <span>Discard</span>
        </div>
        {state.trumpCard && (
          <div className="pile">
            <CardView card={state.trumpCard} small />
            <span>Bottom trump</span>
          </div>
        )}
      </div>

      <div className="pair-grid">
        {bout?.table.length ? (
          bout.table.map((pair) => (
            <article className={`table-pair ${pair.defense ? "covered" : ""}`} key={pair.id}>
              <span className="pair-id">#{pair.id}</span>
              <div className="pair-cards">
                <CardView card={pair.attack} />
                <CardView card={pair.defense} muted={!pair.defense} />
              </div>
              <small>
                {pair.attacker.toUpperCase()}
                {pair.defender ? ` -> ${pair.defender.toUpperCase()}` : ""}
              </small>
            </article>
          ))
        ) : (
          <div className="empty-table">Waiting for the opening attack.</div>
        )}
      </div>
    </section>
  );
}
