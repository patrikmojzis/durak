import { AgentDocs } from "./AgentDocs";
import { CreateGame } from "./CreateGame";
import { GamePage } from "./GamePage";

export function App() {
  if (window.location.pathname === "/agents") {
    return <AgentDocs />;
  }

  const match = window.location.pathname.match(/^\/g\/([^/]+)$/);
  if (match) {
    return <GamePage gameId={match[1]} />;
  }
  return <CreateGame />;
}
