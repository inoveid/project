import { useState } from "react";
import { useAuthLogout, useAuthStatus } from "../hooks/useAuth";
import { AuthLoginModal } from "./AuthLoginModal";

export function AuthStatusBadge() {
  const { data: authStatus, isLoading } = useAuthStatus();
  const logout = useAuthLogout();
  const [showModal, setShowModal] = useState(false);

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-400">
        <span className="w-2 h-2 rounded-full bg-gray-400" />
        Checking...
      </div>
    );
  }

  if (authStatus?.logged_in) {
    return (
      <div className="flex items-center gap-2 text-sm">
        <span className="w-2 h-2 rounded-full bg-green-500" />
        <span className="text-gray-700">{authStatus.email}</span>
        <button
          onClick={() => logout.mutate()}
          disabled={logout.isPending}
          className="text-gray-400 hover:text-gray-600 text-xs"
        >
          Logout
        </button>
      </div>
    );
  }

  return (
    <>
      <div className="flex items-center gap-2 text-sm">
        <span className="w-2 h-2 rounded-full bg-red-500" />
        <span className="text-gray-500">Not authenticated</span>
        <button
          onClick={() => setShowModal(true)}
          className="text-blue-600 hover:text-blue-800 text-xs font-medium"
        >
          Login
        </button>
      </div>
      {showModal && <AuthLoginModal onClose={() => setShowModal(false)} />}
    </>
  );
}
