export type Player = `p${number}`;
export type DeckType = "36" | "52";
export type FirstAttacker = "lowest-trump" | "random";

export type CardInfo = {
  rank: string;
  suit: string;
  code: string;
};

export type TablePair = {
  id: number;
  attacker: Player;
  attack: CardInfo;
  defender: Player | null;
  defense: CardInfo | null;
};

export type BoutState = {
  attacker: Player;
  defender: Player;
  defenderHandCount: number;
  passed: Player[];
  table: TablePair[];
};

export type AttackAction = {
  type: "attack";
  card: string;
  note?: string;
};

export type DefendAction = {
  type: "defend";
  attackId: number;
  card: string;
  note?: string;
};

export type ThrowInAction = {
  type: "throw_in";
  card: string;
  note?: string;
};

export type PassAction = {
  type: "pass";
  note?: string;
};

export type TakeAction = {
  type: "take";
  note?: string;
};

export type ReadyAction = {
  type: "ready";
  note?: string;
};

export type GameAction = AttackAction | DefendAction | ThrowInAction | PassAction | TakeAction | ReadyAction;

export type PlayerInfo = Record<
  Player,
  {
    name: string;
    cardCount: number;
    human: boolean;
    finished: boolean;
  }
>;

export type GameState = {
  id: string;
  version: number;
  status: "active" | "finished";
  viewer: Player | "spectator";
  canAct: boolean;
  currentActors: Player[];
  turn: Player | null;
  players: Player[];
  playerInfo: PlayerInfo;
  humanSeats: Player[];
  deckType: DeckType;
  cramped: boolean;
  trumpSuit: string;
  trumpCard: CardInfo | null;
  stockCount: number;
  discardCount: number;
  bout: BoutState | null;
  hand: string[];
  legalActions: GameAction[];
  finished: Player[];
  result: "durak" | "no_durak" | null;
  durak: Player | null;
  history: Array<Record<string, unknown>>;
  finalHands?: Record<Player, string[]>;
  initialHands?: Record<Player, string[]>;
  replay?: Array<Record<string, unknown>>;
  links: Record<"self" | "legalActions" | "boardText" | "boardImage" | "wait" | "action", string>;
};

export type AgentConfig = {
  gameId: string;
  player: Player;
  token: string;
  authorization: string;
  state: string;
  legalActions: string;
  boardText: string;
  boardImage: string;
  wait: string;
  action: string;
  stateUrl: string;
  legalActionsUrl: string;
  boardTextUrl: string;
  boardImageUrl: string;
  waitUrl: string;
  actionUrl: string;
};

export type CreateGamePayload = {
  playerCount: number;
  deckType: DeckType;
  humanSeats: Player[];
  names: Partial<Record<Player, string>>;
  firstAttacker: FirstAttacker;
};

export type CreateGameResponse = {
  gameId: string;
  status: "active";
  players: Player[];
  playerInfo: PlayerInfo;
  humanSeats: Player[];
  deckType: DeckType;
  cramped: boolean;
  trumpSuit: string;
  browserUrl: string;
  spectatorUrl: string;
  playerUrls: Record<Player | "spectator", string>;
  agentConfigs: Partial<Record<Player, AgentConfig>>;
};
