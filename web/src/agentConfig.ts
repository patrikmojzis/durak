import type { AgentConfig, Player } from "./types";

export const agentConfigsStorageKey = (gameId: string) => `durak:agent-configs:${gameId}`;

export function saveAgentConfigs(gameId: string, configs: Partial<Record<Player, AgentConfig>>) {
  try {
    sessionStorage.setItem(agentConfigsStorageKey(gameId), JSON.stringify(configs));
  } catch {
    // Handoff convenience only.
  }
}

export function loadAgentConfigs(gameId: string): Partial<Record<Player, AgentConfig>> {
  try {
    const raw = sessionStorage.getItem(agentConfigsStorageKey(gameId));
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Partial<Record<Player, AgentConfig>>;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

export function agentConfigJson(config: AgentConfig): string {
  return JSON.stringify({ [config.player]: config }, null, 2);
}

export function allAgentConfigsJson(configs: Partial<Record<Player, AgentConfig>>): string {
  return JSON.stringify(configs, null, 2);
}

export function waitUrlWithSince(config: AgentConfig, since = "{version}"): string {
  const joiner = config.waitUrl.includes("?") ? "&" : "?";
  return `${config.waitUrl}${joiner}since=${since}`;
}

export function agentQuickStart(config: AgentConfig): string {
  return [
    `You are playing Podkidnoy Durak as ${config.player.toUpperCase()}.`,
    "",
    "Rules in this table:",
    "- 6-card hands, no transfer.",
    "- All non-defenders may throw in.",
    "- Throw-ins must match ranks already on the table.",
    "- Max attack cards equals defender's hand count at bout start.",
    "- You only see your hand plus public info. Do not infer hidden hands from absent data.",
    "",
    "Loop:",
    `1. Read state: GET ${config.stateUrl}`,
    `2. If canAct is false, wait: GET ${waitUrlWithSince(config)}`,
    `3. When canAct is true, choose exactly one action from: GET ${config.legalActionsUrl}`,
    `4. Submit it: POST ${config.actionUrl}`,
    "",
    "Readable views:",
    `- Text: ${config.boardTextUrl}`,
    `- Image: ${config.boardImageUrl}`,
    "",
    "Optional: include a short private note in the POST body as `note`; notes reveal only after the game.",
    `Authorization: ${config.authorization}`
  ].join("\n");
}

export function agentPacket(config: AgentConfig): string {
  return [agentQuickStart(config), "", "Full config JSON:", agentConfigJson(config)].join("\n");
}

export function createAgentGameExample(origin: string): string {
  return [
    `curl -s -X POST "${origin}/api/games" \\`,
    '  -H "Content-Type: application/json" \\',
    "  -d '{\"playerCount\":4,\"deckType\":\"36\",\"humanSeats\":[],\"names\":{},\"firstAttacker\":\"lowest-trump\"}'"
  ].join("\n");
}
