from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import random
from typing import Literal

Player = str
DeckType = Literal["36", "52"]
FirstAttacker = Literal["lowest-trump", "random"]

HAND_SIZE = 6
MIN_PLAYERS = 2
DEFAULT_PLAYERS = 4
MAX_PLAYERS = 6
SUITS = ("S", "H", "D", "C")
SUIT_NAMES = {"S": "spades", "H": "hearts", "D": "diamonds", "C": "clubs"}
SUIT_SYMBOLS = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}
RANKS_36 = ("6", "7", "8", "9", "10", "J", "Q", "K", "A")
RANKS_52 = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")


class IllegalAction(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Card:
    rank: str
    suit: str

    @property
    def code(self) -> str:
        return f"{self.rank}{self.suit}"


@dataclass(slots=True)
class TablePair:
    id: int
    attacker: Player
    attack: Card
    defender: Player | None = None
    defense: Card | None = None


@dataclass(slots=True)
class Bout:
    attacker: Player
    defender: Player
    defender_hand_count: int
    table: list[TablePair] = field(default_factory=list)
    passed: list[Player] = field(default_factory=list)


@dataclass(slots=True)
class GameState:
    id: str
    players: list[Player]
    names: dict[Player, str]
    human_seats: list[Player]
    deck_type: DeckType
    trump_suit: str
    trump_card: Card | None
    hands: dict[Player, list[Card]]
    stock: list[Card]
    discard: list[Card]
    bout: Bout | None
    result: str | None = None
    durak: Player | None = None
    finished: list[Player] = field(default_factory=list)
    version: int = 0
    next_attack_id: int = 1
    tokens: dict[str, str] = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)
    initial_hands: dict[Player, list[Card]] = field(default_factory=dict)
    cramped: bool = False
    created_at: str | None = None
    updated_at: str | None = None


def ranks_for_deck(deck_type: DeckType) -> tuple[str, ...]:
    return RANKS_52 if deck_type == "52" else RANKS_36


def rank_value(rank: str, deck_type: DeckType) -> int:
    return ranks_for_deck(deck_type).index(rank)


def players_for_count(player_count: int) -> list[Player]:
    if player_count < MIN_PLAYERS or player_count > MAX_PLAYERS:
        raise ValueError(f"playerCount must be between {MIN_PLAYERS} and {MAX_PLAYERS}")
    return [f"p{index}" for index in range(1, player_count + 1)]


def card_from_code(code: str, deck_type: DeckType) -> Card:
    raw = code.strip().upper()
    if len(raw) < 2:
        raise ValueError("Card must look like 9H, 10S, AS")
    suit = raw[-1]
    rank = raw[:-1]
    if suit not in SUITS or rank not in ranks_for_deck(deck_type):
        raise ValueError(f"Unknown card {code}")
    return Card(rank, suit)


def cards_to_codes(cards: list[Card]) -> list[str]:
    return [card.code for card in cards]


def sort_hand(cards: list[Card], deck_type: DeckType, trump_suit: str) -> list[Card]:
    return sorted(cards, key=lambda card: (card.suit == trump_suit, SUITS.index(card.suit), rank_value(card.rank, deck_type)))


def make_deck(deck_type: DeckType) -> list[Card]:
    return [Card(rank, suit) for suit in SUITS for rank in ranks_for_deck(deck_type)]


def remove_card(hand: list[Card], wanted: Card) -> list[Card]:
    for index, card in enumerate(hand):
        if card == wanted:
            return [*hand[:index], *hand[index + 1 :]]
    raise IllegalAction(f"{wanted.code} is not in your hand")


def next_player_from(players: list[Player], start: Player) -> Player:
    index = players.index(start)
    return players[(index + 1) % len(players)]


def active_players(state: GameState) -> list[Player]:
    return [player for player in state.players if player not in state.finished]


def first_active_from(state: GameState, start: Player) -> Player:
    if start not in state.players:
        start = state.players[0]
    index = state.players.index(start)
    for offset in range(len(state.players)):
        player = state.players[(index + offset) % len(state.players)]
        if player not in state.finished:
            return player
    raise IllegalAction("No active players remain")


def next_active_after(state: GameState, player: Player) -> Player:
    start = next_player_from(state.players, player)
    return first_active_from(state, start)


def choose_first_attacker(state: GameState, rng: random.Random, first_attacker: FirstAttacker) -> Player:
    if first_attacker == "random":
        return rng.choice(state.players)

    best: tuple[int, int, Player] | None = None
    for player in state.players:
        for card in state.hands[player]:
            if card.suit != state.trump_suit:
                continue
            candidate = (rank_value(card.rank, state.deck_type), state.players.index(player), player)
            if best is None or candidate < best:
                best = candidate
    return best[2] if best else rng.choice(state.players)


def initial_state(
    *,
    game_id: str,
    player_count: int = DEFAULT_PLAYERS,
    deck_type: DeckType = "36",
    human_seats: list[Player] | None = None,
    names: dict[Player, str] | None = None,
    first_attacker: FirstAttacker = "lowest-trump",
    tokens: dict[str, str] | None = None,
    seed: int | None = None,
) -> GameState:
    players = players_for_count(player_count)
    rng: random.Random = random.Random(seed) if seed is not None else random.SystemRandom()  # type: ignore[assignment]
    deck = make_deck(deck_type)
    rng.shuffle(deck)

    hands = {player: [] for player in players}
    for _ in range(HAND_SIZE):
        for player in players:
            if deck:
                hands[player].append(deck.pop(0))

    if deck:
        trump_card = deck.pop(0)
        trump_suit = trump_card.suit
        deck.append(trump_card)
    else:
        trump_card = None
        trump_suit = rng.choice(list(SUITS))

    for player in players:
        hands[player] = sort_hand(hands[player], deck_type, trump_suit)

    state = GameState(
        id=game_id,
        players=players,
        names={player: (names or {}).get(player, player.upper()) for player in players},
        human_seats=[seat for seat in (human_seats or []) if seat in players],
        deck_type=deck_type,
        trump_suit=trump_suit,
        trump_card=trump_card,
        hands=hands,
        stock=deck,
        discard=[],
        bout=None,
        tokens=tokens or {},
        initial_hands={player: list(cards) for player, cards in hands.items()},
        cramped=(deck_type == "36" and player_count >= 6),
    )
    attacker = choose_first_attacker(state, rng, first_attacker)
    defender = next_active_after(state, attacker)
    state.bout = Bout(attacker=attacker, defender=defender, defender_hand_count=len(state.hands[defender]))
    state.history.append(
        {
            "version": 0,
            "type": "deal",
            "players": len(players),
            "deckType": deck_type,
            "trumpSuit": trump_suit,
            "trumpCard": trump_card.code if trump_card else None,
            "attacker": attacker,
            "defender": defender,
        }
    )
    return state


def table_cards(bout: Bout) -> list[Card]:
    cards: list[Card] = []
    for pair in bout.table:
        cards.append(pair.attack)
        if pair.defense:
            cards.append(pair.defense)
    return cards


def table_ranks(bout: Bout) -> set[str]:
    return {card.rank for card in table_cards(bout)}


def undefended_pairs(bout: Bout) -> list[TablePair]:
    return [pair for pair in bout.table if pair.defense is None]


def beats(state: GameState, attack: Card, defense: Card) -> bool:
    if defense.suit == attack.suit and rank_value(defense.rank, state.deck_type) > rank_value(attack.rank, state.deck_type):
        return True
    return attack.suit != state.trump_suit and defense.suit == state.trump_suit


def can_add_attack(bout: Bout) -> bool:
    return len(bout.table) < bout.defender_hand_count


def throw_cards_for(state: GameState, player: Player) -> list[Card]:
    if not state.bout or not state.bout.table or player == state.bout.defender or player in state.bout.passed:
        return []
    if undefended_pairs(state.bout) or not can_add_attack(state.bout):
        return []
    ranks = table_ranks(state.bout)
    return [card for card in state.hands[player] if card.rank in ranks]


def eligible_throwers(state: GameState) -> list[Player]:
    if not state.bout:
        return []
    return [player for player in active_players(state) if player != state.bout.defender and throw_cards_for(state, player)]


def action_signature(action: dict) -> tuple:
    action_type = action.get("type")
    if action_type in ("attack", "throw_in"):
        return (action_type, action.get("card"))
    if action_type == "defend":
        return (action_type, action.get("attackId"), action.get("card"))
    if action_type in ("pass", "take", "ready"):
        return (action_type,)
    return (action_type, action.get("card"), action.get("attackId"))


def legal_actions(state: GameState, player: Player | None = None) -> list[dict]:
    if not player or player not in state.players or state.result or not state.bout:
        return []
    if player in state.finished:
        return []

    bout = state.bout
    actions: list[dict] = []
    pending = undefended_pairs(bout)

    if not bout.table:
        if player == bout.attacker:
            actions.extend({"type": "attack", "card": card.code} for card in state.hands[player])
        return actions

    if player == bout.defender:
        actions.append({"type": "take"})
        for pair in pending:
            actions.extend(
                {"type": "defend", "attackId": pair.id, "card": card.code}
                for card in state.hands[player]
                if beats(state, pair.attack, card)
            )
        if not pending and not eligible_throwers(state):
            actions.append({"type": "ready"})
        return actions

    throws = throw_cards_for(state, player)
    actions.extend({"type": "throw_in", "card": card.code} for card in throws)
    if throws:
        actions.append({"type": "pass"})
    return actions


def actors(state: GameState) -> list[Player]:
    return [player for player in active_players(state) if legal_actions(state, player)]


def public_history(state: GameState) -> list[dict]:
    return [{key: value for key, value in item.items() if key != "note"} for item in state.history]


def append_event(state: GameState, event: dict, note: str | None = None) -> None:
    item = {"version": state.version + 1, **event}
    if note:
        item["note"] = note[:500]
    state.history.append(item)


def draw_one(state: GameState) -> Card | None:
    if not state.stock:
        return None
    card = state.stock.pop(0)
    if state.trump_card and not any(item == state.trump_card for item in state.stock):
        state.trump_card = None
    return card


def draw_order(state: GameState, attacker: Player, defender: Player) -> list[Player]:
    out: list[Player] = []
    current = attacker
    for _ in range(len(state.players)):
        if current not in state.finished and current not in out:
            out.append(current)
        current = next_player_from(state.players, current)
    if defender in out:
        out = [player for player in out if player != defender]
        out.append(defender)
    return out


def draw_up(state: GameState, attacker: Player, defender: Player) -> None:
    for player in draw_order(state, attacker, defender):
        while len(state.hands[player]) < HAND_SIZE and state.stock:
            card = draw_one(state)
            if card:
                state.hands[player].append(card)
        state.hands[player] = sort_hand(state.hands[player], state.deck_type, state.trump_suit)


def refresh_finished_and_result(state: GameState) -> None:
    if state.stock:
        return
    for player in state.players:
        if player not in state.finished and not state.hands[player]:
            state.finished.append(player)

    remaining = [player for player in state.players if player not in state.finished]
    if len(remaining) == 0:
        state.result = "no_durak"
        state.durak = None
        state.bout = None
    elif len(remaining) == 1:
        state.result = "durak"
        state.durak = remaining[0]
        state.bout = None


def start_next_bout(state: GameState, candidate_attacker: Player) -> None:
    refresh_finished_and_result(state)
    if state.result:
        return
    attacker = first_active_from(state, candidate_attacker)
    defender = next_active_after(state, attacker)
    state.bout = Bout(attacker=attacker, defender=defender, defender_hand_count=len(state.hands[defender]))
    append_event(
        state,
        {
            "type": "bout_start",
            "attacker": attacker,
            "defender": defender,
            "defenderHandCount": len(state.hands[defender]),
        },
    )


def finish_bout(state: GameState, defender_took: bool) -> None:
    if not state.bout:
        raise IllegalAction("No active bout")

    bout = state.bout
    cards = table_cards(bout)
    if defender_took:
        state.hands[bout.defender].extend(cards)
        state.hands[bout.defender] = sort_hand(state.hands[bout.defender], state.deck_type, state.trump_suit)
        append_event(state, {"type": "bout_taken", "defender": bout.defender, "cards": cards_to_codes(cards)})
        candidate = next_player_from(state.players, bout.defender)
    else:
        state.discard.extend(cards)
        append_event(state, {"type": "bout_defended", "defender": bout.defender, "cards": cards_to_codes(cards)})
        candidate = bout.defender

    attacker = bout.attacker
    defender = bout.defender
    state.bout = None
    draw_up(state, attacker, defender)
    start_next_bout(state, candidate)


def exact_action_is_legal(state: GameState, player: Player, action: dict) -> bool:
    wanted = action_signature(action)
    return any(action_signature(item) == wanted for item in legal_actions(state, player))


def apply_action(state: GameState, player: Player, action: dict) -> GameState:
    if state.result:
        raise IllegalAction("Game is already finished")
    if player not in state.players:
        raise IllegalAction("Unknown player")
    if not state.bout:
        raise IllegalAction("No active bout")
    if not exact_action_is_legal(state, player, action):
        raise IllegalAction("Illegal action")

    next_state = deepcopy(state)
    bout = next_state.bout
    if not bout:
        raise IllegalAction("No active bout")

    action_type = action.get("type")
    note = action.get("note") if isinstance(action.get("note"), str) else None

    if action_type == "attack":
        card = card_from_code(str(action.get("card")), next_state.deck_type)
        next_state.hands[player] = remove_card(next_state.hands[player], card)
        pair = TablePair(id=next_state.next_attack_id, attacker=player, attack=card)
        next_state.next_attack_id += 1
        bout.table.append(pair)
        append_event(next_state, {"type": "attack", "player": player, "attackId": pair.id, "card": card.code}, note)

    elif action_type == "throw_in":
        card = card_from_code(str(action.get("card")), next_state.deck_type)
        next_state.hands[player] = remove_card(next_state.hands[player], card)
        pair = TablePair(id=next_state.next_attack_id, attacker=player, attack=card)
        next_state.next_attack_id += 1
        bout.table.append(pair)
        append_event(next_state, {"type": "throw_in", "player": player, "attackId": pair.id, "card": card.code}, note)

    elif action_type == "defend":
        attack_id = int(action.get("attackId"))
        card = card_from_code(str(action.get("card")), next_state.deck_type)
        target = next((pair for pair in bout.table if pair.id == attack_id), None)
        if not target:
            raise IllegalAction("Unknown attackId")
        next_state.hands[player] = remove_card(next_state.hands[player], card)
        target.defender = player
        target.defense = card
        append_event(next_state, {"type": "defend", "player": player, "attackId": attack_id, "card": card.code}, note)

    elif action_type == "pass":
        if player not in bout.passed:
            bout.passed.append(player)
        append_event(next_state, {"type": "pass", "player": player}, note)

    elif action_type == "take":
        append_event(next_state, {"type": "take", "player": player}, note)
        finish_bout(next_state, defender_took=True)

    elif action_type == "ready":
        append_event(next_state, {"type": "ready", "player": player}, note)
        finish_bout(next_state, defender_took=False)

    else:
        raise IllegalAction("Unknown action type")

    next_state.version += 1
    return next_state


def card_to_dict(card: Card | None) -> dict | None:
    if card is None:
        return None
    return {"rank": card.rank, "suit": card.suit, "code": card.code}


def pair_to_dict(pair: TablePair) -> dict:
    return {
        "id": pair.id,
        "attacker": pair.attacker,
        "attack": card_to_dict(pair.attack),
        "defender": pair.defender,
        "defense": card_to_dict(pair.defense),
    }


def bout_to_dict(bout: Bout | None) -> dict | None:
    if not bout:
        return None
    return {
        "attacker": bout.attacker,
        "defender": bout.defender,
        "defenderHandCount": bout.defender_hand_count,
        "passed": list(bout.passed),
        "table": [pair_to_dict(pair) for pair in bout.table],
    }


def state_to_dict(state: GameState) -> dict:
    return {
        "id": state.id,
        "players": state.players,
        "names": state.names,
        "humanSeats": state.human_seats,
        "deckType": state.deck_type,
        "trumpSuit": state.trump_suit,
        "trumpCard": card_to_dict(state.trump_card),
        "hands": {player: cards_to_codes(cards) for player, cards in state.hands.items()},
        "stock": cards_to_codes(state.stock),
        "discard": cards_to_codes(state.discard),
        "bout": bout_to_dict(state.bout),
        "result": state.result,
        "durak": state.durak,
        "finished": state.finished,
        "version": state.version,
        "nextAttackId": state.next_attack_id,
        "tokens": state.tokens,
        "history": state.history,
        "initialHands": {player: cards_to_codes(cards) for player, cards in state.initial_hands.items()},
        "cramped": state.cramped,
        "createdAt": state.created_at,
        "updatedAt": state.updated_at,
    }


def card_from_dict(raw: dict | None, deck_type: DeckType) -> Card | None:
    if not raw:
        return None
    return card_from_code(str(raw["code"]), deck_type)


def pair_from_dict(raw: dict, deck_type: DeckType) -> TablePair:
    return TablePair(
        id=int(raw["id"]),
        attacker=str(raw["attacker"]),
        attack=card_from_dict(raw["attack"], deck_type),  # type: ignore[arg-type]
        defender=raw.get("defender"),
        defense=card_from_dict(raw.get("defense"), deck_type),
    )


def bout_from_dict(raw: dict | None, deck_type: DeckType) -> Bout | None:
    if not raw:
        return None
    return Bout(
        attacker=str(raw["attacker"]),
        defender=str(raw["defender"]),
        defender_hand_count=int(raw["defenderHandCount"]),
        passed=list(raw.get("passed", [])),
        table=[pair_from_dict(item, deck_type) for item in raw.get("table", [])],
    )


def state_from_dict(raw: dict) -> GameState:
    deck_type: DeckType = raw["deckType"]
    return GameState(
        id=raw["id"],
        players=list(raw["players"]),
        names=dict(raw["names"]),
        human_seats=list(raw.get("humanSeats", [])),
        deck_type=deck_type,
        trump_suit=raw["trumpSuit"],
        trump_card=card_from_dict(raw.get("trumpCard"), deck_type),
        hands={player: [card_from_code(code, deck_type) for code in cards] for player, cards in raw["hands"].items()},
        stock=[card_from_code(code, deck_type) for code in raw["stock"]],
        discard=[card_from_code(code, deck_type) for code in raw["discard"]],
        bout=bout_from_dict(raw.get("bout"), deck_type),
        result=raw.get("result"),
        durak=raw.get("durak"),
        finished=list(raw.get("finished", [])),
        version=int(raw["version"]),
        next_attack_id=int(raw["nextAttackId"]),
        tokens=dict(raw["tokens"]),
        history=list(raw["history"]),
        initial_hands={
            player: [card_from_code(code, deck_type) for code in cards] for player, cards in raw.get("initialHands", {}).items()
        },
        cramped=bool(raw.get("cramped", False)),
        created_at=raw.get("createdAt"),
        updated_at=raw.get("updatedAt"),
    )
