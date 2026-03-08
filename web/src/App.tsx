import { Routes, Route } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Dashboard } from "./pages/Dashboard";
import { TeamPage } from "./pages/TeamPage";
import { ChatPage } from "./pages/ChatPage";
import { EvalDashboard } from "./pages/EvalDashboard";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/teams/:id" element={<TeamPage />} />
        <Route path="/chat/:sessionId" element={<ChatPage />} />
        <Route path="/eval" element={<EvalDashboard />} />
      </Route>
    </Routes>
  );
}
