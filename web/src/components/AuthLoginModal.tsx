import { useEffect, useRef, useState } from "react";
import { startAuthLogin, submitAuthCode } from "../api/auth";
import { useAuthStatus } from "../hooks/useAuth";

interface AuthLoginModalProps {
  onClose: () => void;
}

export function AuthLoginModal({ onClose }: AuthLoginModalProps) {
  const { data: authStatus } = useAuthStatus(true);
  const [authUrl, setAuthUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [codeSubmitted, setCodeSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const loginCalled = useRef(false);

  useEffect(() => {
    if (loginCalled.current) return;
    loginCalled.current = true;

    startAuthLogin()
      .then((data) => setAuthUrl(data.auth_url))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to start login"));
  }, []);

  useEffect(() => {
    if (authStatus?.logged_in) {
      onClose();
    }
  }, [authStatus?.logged_in, onClose]);

  async function handleSubmitCode() {
    if (!code.trim()) return;
    setSubmitting(true);
    try {
      await submitAuthCode(code);
      setCodeSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit code");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-lg p-6 max-w-md w-full mx-4">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Claude Authentication
        </h2>

        {!authUrl && !error && (
          <p className="text-sm text-gray-600">Starting authentication...</p>
        )}

        {authUrl && (
          <div className="space-y-3">
            <p className="text-sm text-gray-600">
              Open the URL in a browser to complete authentication
            </p>
            <p className="text-xs text-gray-400 break-all">{authUrl}</p>
            <button
              onClick={() => window.open(authUrl, "_blank")}
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
              {codeSubmitted ? (
                <p className="text-sm text-green-600 text-center">
                  Code submitted, waiting...
                </p>
              ) : (
                <button
                  onClick={handleSubmitCode}
                  disabled={!code.trim() || submitting}
                  className="w-full bg-green-600 text-white px-4 py-2 rounded text-sm hover:bg-green-700 disabled:opacity-50"
                >
                  {submitting ? "Submitting..." : "Submit code"}
                </button>
              )}
            </div>
          </div>
        )}

        {error && (
          <div className="space-y-3">
            <p className="text-sm text-red-600">{error}</p>
            <button
              onClick={() => {
                setError(null);
                setAuthUrl(null);
                loginCalled.current = false;
                startAuthLogin()
                  .then((data) => {
                    loginCalled.current = true;
                    setAuthUrl(data.auth_url);
                  })
                  .catch((err) =>
                    setError(err instanceof Error ? err.message : "Failed to start login")
                  );
              }}
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
