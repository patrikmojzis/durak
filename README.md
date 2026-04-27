# Durak Web + Agent API

Browser-playable Podkidnoy Durak with tokenized API seats for external agents.

## Local Development

```bash
python3 -m venv .venv
.venv/bin/pip install -r server/requirements-dev.txt
PYTHONPATH=server DURAK_DB_PATH=data/dev.sqlite3 .venv/bin/uvicorn app.main:app --reload --app-dir server
```

In another terminal:

```bash
cd web
pnpm install
pnpm dev
```

Open `http://localhost:5173`.

## Rules

- Podkidnoy Durak, no transfer.
- 2-6 seats.
- Default 36-card deck, optional 52-card deck.
- 6-card hands.
- All non-defenders may throw in.
- Throw-ins must match ranks already on the table.
- Attack-card cap is the defender's hand count at bout start.
- Last player with cards is the durak; if everyone empties together, there is no durak.

## Docker

```bash
cp .env.example .env
# edit PUBLIC_BASE_URL in .env
docker compose up -d --build
```

The app listens on port `8000`. SQLite persists in the `durak_data` Docker volume.
By default Compose binds to `127.0.0.1:8000`, which is right behind Caddy or Nginx.

## Production Deploy

Set:

```bash
PUBLIC_BASE_URL=https://durak.example.com
HOST_BIND=127.0.0.1
HOST_PORT=8000
```

Caddy reverse proxy:

```caddy
durak.example.com {
  reverse_proxy 127.0.0.1:8000
}
```

Nginx needs long-poll friendly timeouts:

```nginx
proxy_read_timeout 60s;
proxy_send_timeout 60s;
```

## API Shape

- `POST /api/games`
- `GET /api/games/{id}`
- `GET /api/games/{id}/legal-actions`
- `GET /api/games/{id}/board.txt`
- `GET /api/games/{id}/board.png`
- `GET /api/games/{id}/wait?since={version}`
- `POST /api/games/{id}/actions`

Player and spectator access use bearer tokens returned by game creation. During active games, player state reveals only that player's hand plus public information. Full hands and private notes reveal only after the game finishes.

## Agent Loop

Give an agent exactly one player config. Then it should:

1. `GET stateUrl` and read `version`, `canAct`, `currentActors`, `result`.
2. If `canAct` is false, call `GET waitUrl&since={version}`.
3. If `canAct` is true, call `GET legalActionsUrl`.
4. Pick one legal action and `POST actionUrl`.
5. Repeat from step 1.

Use `boardTextUrl` for compact reasoning and `boardImageUrl` for multimodal table inspection.

The browser also serves an agent quick-start page at `/agents`.
