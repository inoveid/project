import { Routes, Route, Navigate } from "react-router-dom";
import { Layout } from "./components/Layout";
import { AuthGuard } from "./components/AuthGuard";
import { GlobalChatWidget } from "./components/GlobalChatWidget";
import { NotificationLayer } from "./components/notifications/NotificationLayer";
import { ToastProvider } from "./hooks/useToast";
import { hasToken } from "./api/client";
import { Dashboard } from "./pages/Dashboard";
import { CanvasPage } from "./pages/CanvasPage";
import { ChatPage } from "./pages/ChatPage";
import { EvalDashboard } from "./pages/EvalDashboard";
import { BusinessListPage } from "./pages/BusinessListPage";
import { BusinessPage } from "./pages/BusinessPage";
import { LoginPage } from "./pages/LoginPage";

function AuthWidgets() {
  if (!hasToken()) return null;
  return (
    <>
      <GlobalChatWidget />
      <NotificationLayer />
    </>
  );
}

export function App() {
  return (
    <ToastProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          element={
            <AuthGuard>
              <Layout />
            </AuthGuard>
          }
        >
          <Route path="/" element={<Dashboard />} />
          <Route path="/teams" element={<CanvasPage />} />
          <Route path="/teams/:id" element={<Navigate to="/teams" replace />} />
          <Route path="/chat/:sessionId" element={<ChatPage />} />
          <Route path="/eval" element={<EvalDashboard />} />
          <Route path="/businesses" element={<BusinessListPage />} />
          <Route path="/businesses/:businessId" element={<BusinessPage />} />
        </Route>
      </Routes>
      <AuthWidgets />
    </ToastProvider>
  );
}
