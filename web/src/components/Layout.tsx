import { Outlet, Link, useLocation } from "react-router-dom";
import { AuthStatusBadge } from "./AuthStatusBadge";
import { useCurrentUser, useUserLogout } from "../hooks/useAuth";

const NAV_ITEMS = [
  { path: "/", label: "Dashboard" },
  { path: "/teams", label: "Teams" },
  { path: "/businesses", label: "Businesses" },
  { path: "/eval", label: "Evaluations" },
] as const;

export function Layout() {
  const location = useLocation();
  const isFullWidth = location.pathname === "/teams";
  const { data: user } = useCurrentUser();
  const logout = useUserLogout();

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-6">
          <Link to="/" className="text-xl font-bold text-gray-900">
            Agent Console
          </Link>
          <nav className="flex gap-4">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={
                  location.pathname === item.path
                    ? "text-sm font-medium text-blue-600"
                    : "text-sm text-gray-600 hover:text-gray-900"
                }
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <AuthStatusBadge />
            {user && (
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-600">{user.name}</span>
                <button
                  onClick={() => logout.mutate()}
                  className="text-xs text-gray-400 hover:text-gray-700 border px-2 py-1 rounded"
                >
                  Выйти
                </button>
              </div>
            )}
          </div>
        </div>
      </header>
      <main className={isFullWidth ? "px-4 py-2" : "max-w-7xl mx-auto px-4 py-6"}>
        <Outlet />
      </main>
    </div>
  );
}
