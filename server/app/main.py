from __future__ import annotations

import asyncio
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .engine import (
    DEFAULT_PLAYERS,
    MAX_PLAYERS,
    MIN_PLAYERS,
    DeckType,
    FirstAttacker,
    GameState,
    IllegalAction,
    Player,
    actors,
    apply_action,
    card_to_dict,
    cards_to_codes,
    initial_state,
    legal_actions,
    public_history,
)
from .render import render_board_png, render_board_text
from .storage import create_game, get_game, init_db, save_game


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Durak Web + Agent API", lifespan=lifespan)
ACTION_LOCK = asyncio.Lock()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_route() -> dict[str, str]:
    return {"status": "ok"}


class GameCreate(BaseModel):
    playerCount: int = Field(default=DEFAULT_PLAYERS, ge=MIN_PLAYERS, le=MAX_PLAYERS)
    deckType: DeckType = "36"
    humanSeats: list[str] = Field(default_factory=list)
    names: dict[str, str] = Field(default_factory=dict)
    firstAttacker: FirstAttacker = "lowest-trump"


class ActionIn(BaseModel):
    type: Literal["attack", "defend", "throw_in", "pass", "take", "ready"]
    card: str | None = None
    attackId: int | None = None
    note: str | None = Field(default=None, max_length=500)

    def to_engine_action(self) -> dict:
        action: dict = {"type": self.type}
        if self.type in ("attack", "throw_in"):
            if not self.card:
                raise ValueError(f"{self.type} requires `card`")
            action["card"] = self.card
        elif self.type == "defend":
            if not self.card or self.attackId is None:
                raise ValueError("defend requires `attackId` and `card`")
            action["card"] = self.card
            action["attackId"] = self.attackId
        if self.note:
            action["note"] = self.note
        return action


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(9).replace('-', '').replace('_', '')}"


def public_base_url(request: Request) -> str:
    configured = os.getenv("PUBLIC_BASE_URL")
    if configured:
        return configured.rstrip("/")
    return str(request.base_url).rstrip("/")


def token_from_request(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    token = request.query_params.get("token")
    return token.strip() if token else None


def role_for_token(state: GameState, token: str | None) -> str:
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    for role, value in state.tokens.items():
        if secrets.compare_digest(value, token):
            return role
    raise HTTPException(status_code=403, detail="Invalid token")


def require_game(game_id: str) -> GameState:
    state = get_game(game_id)
    if not state:
        raise HTTPException(status_code=404, detail="Game not found")
    return state


def path_with_token(base: str, path: str, token: str) -> str:
    return f"{base}{path}?token={token}"


def agent_config(base: str, state: GameState, player: Player) -> dict:
    token = state.tokens[player]
    game_path = f"/api/games/{state.id}"
    return {
        "gameId": state.id,
        "player": player,
        "token": token,
        "authorization": f"Bearer {token}",
        "state": f"{base}{game_path}",
        "legalActions": f"{base}{game_path}/legal-actions",
        "boardText": f"{base}{game_path}/board.txt",
        "boardImage": f"{base}{game_path}/board.png",
        "wait": f"{base}{game_path}/wait",
        "action": f"{base}{game_path}/actions",
        "stateUrl": path_with_token(base, game_path, token),
        "legalActionsUrl": path_with_token(base, f"{game_path}/legal-actions", token),
        "boardTextUrl": path_with_token(base, f"{game_path}/board.txt", token),
        "boardImageUrl": path_with_token(base, f"{game_path}/board.png", token),
        "waitUrl": path_with_token(base, f"{game_path}/wait", token),
        "actionUrl": path_with_token(base, f"{game_path}/actions", token),
    }


def public_player_summary(state: GameState) -> dict:
    return {
        player: {
            "name": state.names[player],
            "cardCount": len(state.hands[player]),
            "human": player in state.human_seats,
            "finished": player in state.finished,
        }
        for player in state.players
    }


def state_response(request: Request, state: GameState, viewer: str) -> dict:
    base = public_base_url(request)
    player = viewer if viewer in state.players else None
    current_actors = actors(state)
    can_act = bool(player and player in current_actors)
    actions = legal_actions(state, player) if player else []
    status = "finished" if state.result else "active"

    body = {
        "id": state.id,
        "version": state.version,
        "status": status,
        "viewer": viewer,
        "canAct": can_act,
        "currentActors": current_actors,
        "turn": current_actors[0] if current_actors else None,
        "players": state.players,
        "playerInfo": public_player_summary(state),
        "humanSeats": state.human_seats,
        "deckType": state.deck_type,
        "cramped": state.cramped,
        "trumpSuit": state.trump_suit,
        "trumpCard": card_to_dict(state.trump_card),
        "stockCount": len(state.stock),
        "discardCount": len(state.discard),
        "bout": {
            "attacker": state.bout.attacker,
            "defender": state.bout.defender,
            "defenderHandCount": state.bout.defender_hand_count,
            "passed": list(state.bout.passed),
            "table": [
                {
                    "id": pair.id,
                    "attacker": pair.attacker,
                    "attack": card_to_dict(pair.attack),
                    "defender": pair.defender,
                    "defense": card_to_dict(pair.defense),
                }
                for pair in state.bout.table
            ],
        }
        if state.bout
        else None,
        "hand": cards_to_codes(state.hands[player]) if player else [],
        "legalActions": actions,
        "finished": state.finished,
        "result": state.result,
        "durak": state.durak,
        "history": public_history(state)[-40:],
        "links": {
            "self": f"{base}/api/games/{state.id}",
            "legalActions": f"{base}/api/games/{state.id}/legal-actions",
            "boardText": f"{base}/api/games/{state.id}/board.txt",
            "boardImage": f"{base}/api/games/{state.id}/board.png",
            "wait": f"{base}/api/games/{state.id}/wait",
            "action": f"{base}/api/games/{state.id}/actions",
        },
    }

    if state.result:
        body["finalHands"] = {seat: cards_to_codes(cards) for seat, cards in state.hands.items()}
        body["initialHands"] = {seat: cards_to_codes(cards) for seat, cards in state.initial_hands.items()}
        body["replay"] = state.history

    return body


@app.post("/api/games")
def create_game_route(payload: GameCreate, request: Request) -> dict:
    players = [f"p{index}" for index in range(1, payload.playerCount + 1)]
    human_seats = [seat for seat in payload.humanSeats if seat in players]
    tokens = {player: new_id(player) for player in players}
    tokens["spectator"] = new_id("spec")
    names = {
        player: payload.names.get(player, ("Human" if player in human_seats else f"Agent {player.upper()}"))
        for player in players
    }

    state = initial_state(
        game_id=new_id("g"),
        player_count=payload.playerCount,
        deck_type=payload.deckType,
        human_seats=human_seats,
        names=names,
        first_attacker=payload.firstAttacker,
        tokens=tokens,
    )
    state = create_game(state)

    base = public_base_url(request)
    browser_role = human_seats[0] if human_seats else "spectator"
    return {
        "gameId": state.id,
        "status": "active",
        "players": state.players,
        "playerInfo": public_player_summary(state),
        "humanSeats": state.human_seats,
        "deckType": state.deck_type,
        "cramped": state.cramped,
        "trumpSuit": state.trump_suit,
        "browserUrl": path_with_token(base, f"/g/{state.id}", state.tokens[browser_role]),
        "spectatorUrl": path_with_token(base, f"/g/{state.id}", state.tokens["spectator"]),
        "playerUrls": {
            **{player: path_with_token(base, f"/g/{state.id}", state.tokens[player]) for player in state.players},
            "spectator": path_with_token(base, f"/g/{state.id}", state.tokens["spectator"]),
        },
        "agentConfigs": {
            player: agent_config(base, state, player) for player in state.players if player not in state.human_seats
        },
    }


@app.get("/api/games/{game_id}")
def get_game_route(game_id: str, request: Request) -> dict:
    state = require_game(game_id)
    viewer = role_for_token(state, token_from_request(request))
    return state_response(request, state, viewer)


@app.get("/api/games/{game_id}/legal-actions")
def legal_actions_route(game_id: str, request: Request) -> dict:
    state = require_game(game_id)
    viewer = role_for_token(state, token_from_request(request))
    player = viewer if viewer in state.players else None
    current_actors = actors(state)
    return {
        "gameId": state.id,
        "version": state.version,
        "viewer": viewer,
        "canAct": bool(player and player in current_actors),
        "currentActors": current_actors,
        "legalActions": legal_actions(state, player) if player else [],
    }


@app.get("/api/games/{game_id}/board.txt", response_class=PlainTextResponse)
def board_text_route(game_id: str, request: Request) -> str:
    state = require_game(game_id)
    viewer = role_for_token(state, token_from_request(request))
    return render_board_text(state, viewer)


@app.get("/api/games/{game_id}/board.png")
def board_png_route(game_id: str, request: Request) -> Response:
    state = require_game(game_id)
    viewer = role_for_token(state, token_from_request(request))
    return Response(content=render_board_png(state, viewer), media_type="image/png")


@app.get("/api/games/{game_id}/wait")
async def wait_route(
    game_id: str,
    request: Request,
    since: int = Query(default=-1),
    timeout: float = Query(default=25, ge=1, le=30),
) -> dict:
    state = require_game(game_id)
    viewer = role_for_token(state, token_from_request(request))
    deadline = asyncio.get_running_loop().time() + timeout

    while state.version <= since and asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(0.4)
        state = require_game(game_id)

    return state_response(request, state, viewer)


@app.post("/api/games/{game_id}/actions")
async def action_route(game_id: str, payload: ActionIn, request: Request) -> dict:
    try:
        action = payload.to_engine_action()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    async with ACTION_LOCK:
        state = require_game(game_id)
        viewer = role_for_token(state, token_from_request(request))
        if viewer not in state.players:
            raise HTTPException(status_code=403, detail="Spectators cannot act")
        try:
            next_state = apply_action(state, viewer, action)
        except (IllegalAction, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        save_game(next_state)
        return state_response(request, next_state, viewer)


WEB_DIST_DIR = Path(os.getenv("WEB_DIST_DIR", Path(__file__).resolve().parents[2] / "web" / "dist"))
if WEB_DIST_DIR.exists() and (WEB_DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST_DIR / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str = ""):
    index = WEB_DIST_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "Durak API is running. Build the web app to serve the browser UI."}
