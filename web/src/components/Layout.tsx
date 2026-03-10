import { Outlet, Link, useLocation } from "react-router-dom";
import { AuthStatusBadge } from "./AuthStatusBadge";

const NAV_ITEMS = [
  { path: "/", label: "Dashboard" },
  { path: "/teams", label: "Teams" },
  { path: "/eval", label: "Evaluations" },
] as const;

export function Layout() {
  const location = useLocation();
  const isFullWidth = location.pathname === "/teams";

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
          <div className="ml-auto">
            <AuthStatusBadge />
          </div>
        </div>
      </header>
      <main className={isFullWidth ? "px-4 py-2" : "max-w-7xl mx-auto px-4 py-6"}>
        <Outlet />
      </main>
    </div>
  );
}
