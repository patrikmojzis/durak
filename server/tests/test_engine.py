from app.engine import (
    Bout,
    Card,
    GameState,
    IllegalAction,
    apply_action,
    cards_to_codes,
    initial_state,
    legal_actions,
    refresh_finished_and_result,
)


def controlled_game() -> GameState:
    state = initial_state(
        game_id="g_test",
        player_count=3,
        deck_type="36",
        human_seats=["p1"],
        names={"p1": "P1", "p2": "P2", "p3": "P3"},
        tokens={"p1": "p1", "p2": "p2", "p3": "p3", "spectator": "s"},
        seed=2,
    )
    state.trump_suit = "S"
    state.trump_card = Card("6", "S")
    state.stock = []
    state.discard = []
    state.finished = []
    state.result = None
    state.durak = None
    state.next_attack_id = 1
    state.bout = Bout(attacker="p1", defender="p2", defender_hand_count=6)
    return state


def test_initial_deal_and_trump_for_36_card_four_player_game() -> None:
    state = initial_state(game_id="g", player_count=4, deck_type="36", seed=1)

    assert len(state.players) == 4
    assert all(len(state.hands[player]) == 6 for player in state.players)
    assert len(state.stock) == 12
    assert state.trump_card is not None
    assert state.trump_suit == state.trump_card.suit
    assert state.bout is not None


def test_six_player_36_card_table_is_cramped_and_has_random_trump_suit() -> None:
    state = initial_state(game_id="g", player_count=6, deck_type="36", seed=1)

    assert state.cramped is True
    assert len(state.stock) == 0
    assert state.trump_card is None
    assert state.trump_suit in {"S", "H", "D", "C"}


def test_lowest_trump_starts_when_available() -> None:
    state = initial_state(game_id="g", player_count=4, deck_type="36", first_attacker="lowest-trump", seed=4)
    trumps = [
        (("6", "7", "8", "9", "10", "J", "Q", "K", "A").index(card.rank), player)
        for player, cards in state.hands.items()
        for card in cards
        if card.suit == state.trump_suit
    ]

    assert state.bout is not None
    assert state.bout.attacker == min(trumps)[1]


def test_valid_same_suit_defense() -> None:
    state = controlled_game()
    state.hands["p1"] = [Card("9", "H")]
    state.hands["p2"] = [Card("10", "H")]

    state = apply_action(state, "p1", {"type": "attack", "card": "9H"})
    state = apply_action(state, "p2", {"type": "defend", "attackId": 1, "card": "10H"})

    assert state.bout is not None
    assert state.bout.table[0].defense == Card("10", "H")


def test_invalid_lower_defense_is_rejected() -> None:
    state = controlled_game()
    state.hands["p1"] = [Card("9", "H")]
    state.hands["p2"] = [Card("8", "H")]

    state = apply_action(state, "p1", {"type": "attack", "card": "9H"})

    try:
        apply_action(state, "p2", {"type": "defend", "attackId": 1, "card": "8H"})
    except IllegalAction as exc:
        assert "Illegal action" in str(exc)
    else:
        raise AssertionError("Expected lower defense to fail")


def test_throw_in_must_match_rank_on_table() -> None:
    state = controlled_game()
    state.hands["p1"] = [Card("9", "H")]
    state.hands["p2"] = [Card("10", "H")]
    state.hands["p3"] = [Card("9", "S"), Card("Q", "D")]

    state = apply_action(state, "p1", {"type": "attack", "card": "9H"})
    state = apply_action(state, "p2", {"type": "defend", "attackId": 1, "card": "10H"})

    actions = legal_actions(state, "p3")
    assert {"type": "throw_in", "card": "9S"} in actions
    assert {"type": "throw_in", "card": "QD"} not in actions


def test_throw_in_cap_uses_defender_starting_hand_count() -> None:
    state = controlled_game()
    state.bout = Bout(attacker="p1", defender="p2", defender_hand_count=1)
    state.hands["p1"] = [Card("9", "H")]
    state.hands["p2"] = [Card("10", "H")]
    state.hands["p3"] = [Card("9", "S")]

    state = apply_action(state, "p1", {"type": "attack", "card": "9H"})
    state = apply_action(state, "p2", {"type": "defend", "attackId": 1, "card": "10H"})

    assert not legal_actions(state, "p3")


def test_take_adds_table_to_defender_and_next_attacker_is_after_defender() -> None:
    state = controlled_game()
    state.hands["p1"] = [Card("9", "H"), Card("8", "C")]
    state.hands["p2"] = [Card("Q", "D")]

    state = apply_action(state, "p1", {"type": "attack", "card": "9H"})
    state = apply_action(state, "p2", {"type": "take"})

    assert "9H" in cards_to_codes(state.hands["p2"])
    assert state.bout is not None
    assert state.bout.attacker == "p3"
    assert state.bout.defender == "p1"


def test_successful_defense_discards_table_and_defender_attacks_next() -> None:
    state = controlled_game()
    state.hands["p1"] = [Card("9", "H"), Card("8", "C")]
    state.hands["p2"] = [Card("10", "H"), Card("Q", "D")]
    state.hands["p3"] = [Card("A", "C")]

    state = apply_action(state, "p1", {"type": "attack", "card": "9H"})
    state = apply_action(state, "p2", {"type": "defend", "attackId": 1, "card": "10H"})
    state = apply_action(state, "p2", {"type": "ready"})

    assert cards_to_codes(state.discard) == ["9H", "10H"]
    assert state.bout is not None
    assert state.bout.attacker == "p2"


def test_draw_order_attacker_then_others_then_defender() -> None:
    state = controlled_game()
    state.stock = [Card("6", "C"), Card("7", "C"), Card("8", "C")]
    state.hands["p1"] = [Card("9", "H"), Card("7", "D"), Card("8", "D"), Card("J", "D"), Card("Q", "D"), Card("K", "D")]
    state.hands["p2"] = [Card("10", "H")]
    state.hands["p3"] = [Card("J", "D"), Card("Q", "D"), Card("K", "D"), Card("A", "D"), Card("6", "D")]

    state = apply_action(state, "p1", {"type": "attack", "card": "9H"})
    state = apply_action(state, "p2", {"type": "defend", "attackId": 1, "card": "10H"})
    state = apply_action(state, "p2", {"type": "ready"})

    assert "6C" in cards_to_codes(state.hands["p1"])
    assert "7C" in cards_to_codes(state.hands["p3"])
    assert "8C" in cards_to_codes(state.hands["p2"])


def test_finished_players_are_skipped_and_last_player_is_durak() -> None:
    state = controlled_game()
    state.stock = []
    state.hands["p1"] = []
    state.hands["p2"] = [Card("A", "S")]
    state.hands["p3"] = []

    refresh_finished_and_result(state)

    assert state.result == "durak"
    assert state.durak == "p2"


def test_no_durak_when_everyone_empties() -> None:
    state = controlled_game()
    state.stock = []
    state.hands = {"p1": [], "p2": [], "p3": []}

    refresh_finished_and_result(state)

    assert state.result == "no_durak"
    assert state.durak is None
