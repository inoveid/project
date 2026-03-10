import { Routes, Route, Navigate } from "react-router-dom";
import { Layout } from "./components/Layout";
import { GlobalChatWidget } from "./components/GlobalChatWidget";
import { Dashboard } from "./pages/Dashboard";
import { CanvasPage } from "./pages/CanvasPage";
import { ChatPage } from "./pages/ChatPage";
import { EvalDashboard } from "./pages/EvalDashboard";
import { BusinessListPage } from "./pages/BusinessListPage";
import { BusinessPage } from "./pages/BusinessPage";

export function App() {
  return (
    <>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/teams" element={<CanvasPage />} />
          <Route path="/teams/:id" element={<Navigate to="/teams" replace />} />
          <Route path="/chat/:sessionId" element={<ChatPage />} />
          <Route path="/eval" element={<EvalDashboard />} />
          <Route path="/businesses" element={<BusinessListPage />} />
          <Route path="/businesses/:businessId" element={<BusinessPage />} />
        </Route>
      </Routes>
      <GlobalChatWidget />
    </>
  );
}
