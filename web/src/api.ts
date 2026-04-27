import type { CreateGamePayload, CreateGameResponse, GameAction, GameState } from "./types";

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.ok) {
    return response.json() as Promise<T>;
  }
  let message = `${response.status} ${response.statusText}`;
  try {
    const body = await response.json();
    message = body.detail || message;
  } catch {
    message = await response.text();
  }
  throw new Error(message);
}

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

export function createGame(payload: CreateGamePayload): Promise<CreateGameResponse> {
  return fetch("/api/games", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  }).then(parseResponse<CreateGameResponse>);
}

export function getGame(gameId: string, token: string): Promise<GameState> {
  return fetch(`/api/games/${gameId}`, { headers: authHeaders(token) }).then(parseResponse<GameState>);
}

export function waitGame(gameId: string, token: string, since: number): Promise<GameState> {
  return fetch(`/api/games/${gameId}/wait?since=${since}`, { headers: authHeaders(token) }).then(parseResponse<GameState>);
}

export function sendAction(gameId: string, token: string, action: GameAction): Promise<GameState> {
  return fetch(`/api/games/${gameId}/actions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify(action)
  }).then(parseResponse<GameState>);
}

export function toLocalGameUrl(url: string): string {
  try {
    const parsed = new URL(url);
    return `${parsed.pathname}${parsed.search}`;
  } catch {
    return url;
  }
}

export async function copyText(text: string): Promise<void> {
  await navigator.clipboard.writeText(text);
}
