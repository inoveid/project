import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthStatusBadge } from "./AuthStatusBadge";
import * as authApi from "../api/auth";

vi.mock("../api/auth", () => ({
  getAuthStatus: vi.fn(),
  startAuthLogin: vi.fn(),
  authLogout: vi.fn(),
}));

function renderComponent() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthStatusBadge />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AuthStatusBadge", () => {
  it("shows loading state", () => {
    vi.mocked(authApi.getAuthStatus).mockReturnValue(new Promise(() => {}));
    renderComponent();
    expect(screen.getByText("Checking...")).toBeInTheDocument();
  });

  it("shows not authenticated state", async () => {
    vi.mocked(authApi.getAuthStatus).mockResolvedValue({
      logged_in: false,
      email: null,
      org_name: null,
      subscription_type: null,
      auth_method: null,
    });
    renderComponent();
    expect(await screen.findByText("Not authenticated")).toBeInTheDocument();
    expect(screen.getByText("Login")).toBeInTheDocument();
  });

  it("shows authenticated state with email", async () => {
    vi.mocked(authApi.getAuthStatus).mockResolvedValue({
      logged_in: true,
      email: "user@example.com",
      org_name: "Acme",
      subscription_type: "pro",
      auth_method: "oauth",
    });
    renderComponent();
    expect(await screen.findByText("user@example.com")).toBeInTheDocument();
    expect(screen.getByText("Logout")).toBeInTheDocument();
  });

  it("opens login modal on Login click", async () => {
    vi.mocked(authApi.getAuthStatus).mockResolvedValue({
      logged_in: false,
      email: null,
      org_name: null,
      subscription_type: null,
      auth_method: null,
    });
    vi.mocked(authApi.startAuthLogin).mockReturnValue(new Promise(() => {}));
    renderComponent();
    const loginButton = await screen.findByText("Login");
    fireEvent.click(loginButton);
    expect(
      await screen.findByText("Claude Authentication"),
    ).toBeInTheDocument();
  });
});
