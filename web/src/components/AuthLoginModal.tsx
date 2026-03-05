import { useEffect, useState } from "react";
import { useAuthCallback, useAuthLogin, useAuthStatus } from "../hooks/useAuth";

interface AuthLoginModalProps {
  onClose: () => void;
}

export function AuthLoginModal({ onClose }: AuthLoginModalProps) {
  const login = useAuthLogin();
  const callback = useAuthCallback();
  const { data: authStatus } = useAuthStatus(true);
  const [code, setCode] = useState("");

  useEffect(() => {
    login.mutate();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (authStatus?.logged_in) {
      onClose();
    }
  }, [authStatus?.logged_in, onClose]);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-lg p-6 max-w-md w-full mx-4">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Claude Authentication
        </h2>

        {login.isPending && (
          <p className="text-sm text-gray-600">Starting authentication...</p>
        )}

        {login.isSuccess && login.data && (
          <div className="space-y-3">
            <p className="text-sm text-gray-600">{login.data.message}</p>
            <p className="text-xs text-gray-400 break-all">
              {login.data.auth_url}
            </p>
            <button
              onClick={() => window.open(login.data.auth_url, "_blank")}
              className="w-full bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700"
            >
              Authorize
            </button>
            <div className="border-t pt-3 mt-3">
              <p className="text-sm text-gray-600 mb-2">
                After authorizing in the browser, paste the code below:
              </p>
              <input
                type="text"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="Enter OAuth code"
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm mb-2"
              />
              {callback.isSuccess ? (
                <p className="text-sm text-green-600 text-center">
                  Code submitted, waiting...
                </p>
              ) : (
                <button
                  onClick={() => callback.mutate(code)}
                  disabled={!code.trim() || callback.isPending}
                  className="w-full bg-green-600 text-white px-4 py-2 rounded text-sm hover:bg-green-700 disabled:opacity-50"
                >
                  {callback.isPending ? "Submitting..." : "Submit code"}
                </button>
              )}
              {callback.isError && (
                <p className="text-sm text-red-600 mt-1">
                  {callback.error instanceof Error
                    ? callback.error.message
                    : "Failed to submit code"}
                </p>
              )}
            </div>
          </div>
        )}

        {login.isError && (
          <div className="space-y-3">
            <p className="text-sm text-red-600">
              {login.error instanceof Error
                ? login.error.message
                : "Authentication failed"}
            </p>
            <button
              onClick={() => login.mutate()}
              className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700"
            >
              Retry
            </button>
          </div>
        )}

        <button
          onClick={onClose}
          className="mt-4 w-full text-sm text-gray-500 hover:text-gray-700"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
