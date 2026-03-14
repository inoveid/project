import { Routes, Route, Navigate, useLocation, useParams, useNavigate } from "react-router-dom";
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
import { TaskPage } from "./pages/TaskPage";
import { TaskModal } from "./components/tasks/TaskModal";

function AuthWidgets() {
  if (!hasToken()) return null;
  return (
    <>
      <GlobalChatWidget />
      <NotificationLayer />
    </>
  );
}

function ModalTaskRoute() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  if (!id) return null;
  return <TaskModal taskId={id} onClose={() => navigate(-1)} />;
}

export function App() {
  const location = useLocation();
  const background = location.state?.background;

  return (
    <ToastProvider>
      <Routes location={background || location}>
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
          <Route path="/tasks/:id" element={<TaskPage />} />
        </Route>
      </Routes>
      {background && (
        <Routes>
          <Route path="/tasks/:id" element={<ModalTaskRoute />} />
        </Routes>
      )}
      <AuthWidgets />
    </ToastProvider>
  );
}
