from fastapi.testclient import TestClient

from app.engine import Bout, Card, initial_state
from app.main import app
from app.render import hand_layout
from app.storage import create_game as store_game
from app.storage import init_db


def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("DURAK_DB_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://testserver")
    init_db()
    return TestClient(app)


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_create_game_returns_tokens_urls_and_agent_configs(tmp_path, monkeypatch) -> None:
    c = client(tmp_path, monkeypatch)

    response = c.post(
        "/api/games",
        json={"playerCount": 4, "deckType": "36", "humanSeats": ["p1"], "names": {"p1": "Patrik"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["players"] == ["p1", "p2", "p3", "p4"]
    assert "browserUrl" in body
    assert "spectatorUrl" in body
    assert "p2" in body["agentConfigs"]
    assert body["agentConfigs"]["p2"]["authorization"].startswith("Bearer p2_")


def test_state_is_partial_and_does_not_leak_other_hands(tmp_path, monkeypatch) -> None:
    c = client(tmp_path, monkeypatch)
    created = c.post("/api/games", json={"playerCount": 3, "deckType": "36", "humanSeats": ["p1"]}).json()
    game_id = created["gameId"]
    p1 = created["playerUrls"]["p1"].split("token=")[1]
    p2 = created["playerUrls"]["p2"].split("token=")[1]

    p1_state = c.get(f"/api/games/{game_id}", headers=auth(p1)).json()
    p2_state = c.get(f"/api/games/{game_id}", headers=auth(p2)).json()

    assert len(p1_state["hand"]) == 6
    assert len(p2_state["hand"]) == 6
    assert p1_state["hand"] != p2_state["hand"]
    assert "finalHands" not in p1_state
    assert "hands" not in p1_state
    assert p1_state["playerInfo"]["p2"]["cardCount"] == 6


def test_spectator_cannot_act_and_missing_token_fails(tmp_path, monkeypatch) -> None:
    c = client(tmp_path, monkeypatch)
    created = c.post("/api/games", json={"playerCount": 2, "deckType": "36", "humanSeats": []}).json()
    game_id = created["gameId"]
    spectator = created["playerUrls"]["spectator"].split("token=")[1]

    assert c.get(f"/api/games/{game_id}").status_code == 401
    response = c.post(f"/api/games/{game_id}/actions", headers=auth(spectator), json={"type": "pass"})

    assert response.status_code == 403


def test_legal_actions_action_rejection_text_png_and_wait(tmp_path, monkeypatch) -> None:
    c = client(tmp_path, monkeypatch)
    created = c.post("/api/games", json={"playerCount": 2, "deckType": "36", "humanSeats": ["p1"]}).json()
    game_id = created["gameId"]
    token = created["playerUrls"][created["players"][0]].split("token=")[1]

    legal = c.get(f"/api/games/{game_id}/legal-actions", headers=auth(token))
    assert legal.status_code == 200
    assert "legalActions" in legal.json()

    rejected = c.post(f"/api/games/{game_id}/actions", headers=auth(token), json={"type": "defend", "attackId": 999, "card": "AS"})
    assert rejected.status_code in {409, 422}

    text = c.get(f"/api/games/{game_id}/board.txt", headers=auth(token))
    assert text.status_code == 200
    assert "Your hand" in text.text

    png = c.get(f"/api/games/{game_id}/board.png", headers=auth(token))
    assert png.status_code == 200
    assert png.headers["content-type"] == "image/png"
    assert png.content.startswith(b"\x89PNG")

    waited = c.get(f"/api/games/{game_id}/wait?since=-1&timeout=1", headers=auth(token))
    assert waited.status_code == 200
    assert waited.json()["id"] == game_id


def test_post_game_replay_reveals_hands_and_private_notes(tmp_path, monkeypatch) -> None:
    c = client(tmp_path, monkeypatch)
    state = initial_state(
        game_id="g_done",
        player_count=2,
        deck_type="36",
        human_seats=["p1"],
        names={"p1": "P1", "p2": "P2"},
        tokens={"p1": "p1_token", "p2": "p2_token", "spectator": "spec_token"},
        seed=1,
    )
    state.trump_suit = "S"
    state.trump_card = None
    state.stock = []
    state.hands = {"p1": [], "p2": [Card("A", "S")]}
    state.initial_hands = {"p1": [Card("9", "H")], "p2": [Card("A", "S")]}
    state.bout = None
    state.result = "durak"
    state.durak = "p2"
    state.history.append({"version": 1, "type": "take", "player": "p2", "note": "I panicked correctly"})
    store_game(state)

    body = c.get("/api/games/g_done", headers=auth("p1_token")).json()

    assert body["status"] == "finished"
    assert body["finalHands"]["p2"] == ["AS"]
    assert body["initialHands"]["p1"] == ["9H"]
    assert body["replay"][-1]["note"] == "I panicked correctly"


def test_query_token_auth_works_for_board_text(tmp_path, monkeypatch) -> None:
    c = client(tmp_path, monkeypatch)
    created = c.post("/api/games", json={"playerCount": 2, "deckType": "36", "humanSeats": ["p1"]}).json()
    game_id = created["gameId"]
    p1 = created["playerUrls"]["p1"].split("token=")[1]

    response = c.get(f"/api/games/{game_id}/board.txt?token={p1}")

    assert response.status_code == 200
    assert "Game:" in response.text


def test_agent_png_hand_layout_supports_large_take_hands() -> None:
    columns, scale, step_x, step_y = hand_layout(52)

    assert columns == 13
    assert scale < 1
    assert step_x > 0
    assert step_y > 0
