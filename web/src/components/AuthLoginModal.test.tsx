import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthLoginModal } from "./AuthLoginModal";
import * as authApi from "../api/auth";

vi.mock("../api/auth", () => ({
  getAuthStatus: vi.fn(),
  startAuthLogin: vi.fn(),
  authLogout: vi.fn(),
}));

function renderComponent(onClose = vi.fn()) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    onClose,
    ...render(
      <QueryClientProvider client={queryClient}>
        <AuthLoginModal onClose={onClose} />
      </QueryClientProvider>,
    ),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AuthLoginModal", () => {
  it("auto-starts login on mount", async () => {
    vi.mocked(authApi.startAuthLogin).mockReturnValue(new Promise(() => {}));
    vi.mocked(authApi.getAuthStatus).mockResolvedValue({
      logged_in: false,
      email: null,
      org_name: null,
      subscription_type: null,
      auth_method: null,
    });
    renderComponent();
    await waitFor(() => {
      expect(authApi.startAuthLogin).toHaveBeenCalledOnce();
    });
  });

  it("shows auth URL and authorize button", async () => {
    vi.mocked(authApi.startAuthLogin).mockResolvedValue({
      auth_url: "https://auth.example.com/oauth",
      message: "Open the URL to authenticate",
    });
    vi.mocked(authApi.getAuthStatus).mockResolvedValue({
      logged_in: false,
      email: null,
      org_name: null,
      subscription_type: null,
      auth_method: null,
    });
    renderComponent();
    expect(
      await screen.findByText("Open the URL to authenticate"),
    ).toBeInTheDocument();
    expect(screen.getByText("Authorize")).toBeInTheDocument();
    expect(
      screen.getByText("https://auth.example.com/oauth"),
    ).toBeInTheDocument();
  });

  it("opens URL in new tab on Authorize click", async () => {
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    vi.mocked(authApi.startAuthLogin).mockResolvedValue({
      auth_url: "https://auth.example.com/oauth",
      message: "Open the URL",
    });
    vi.mocked(authApi.getAuthStatus).mockResolvedValue({
      logged_in: false,
      email: null,
      org_name: null,
      subscription_type: null,
      auth_method: null,
    });
    renderComponent();
    const authorizeButton = await screen.findByText("Authorize");
    fireEvent.click(authorizeButton);
    expect(openSpy).toHaveBeenCalledWith(
      "https://auth.example.com/oauth",
      "_blank",
    );
    openSpy.mockRestore();
  });

  it("auto-closes when logged_in becomes true", async () => {
    vi.mocked(authApi.startAuthLogin).mockResolvedValue({
      auth_url: "https://auth.example.com/oauth",
      message: "Open the URL",
    });
    vi.mocked(authApi.getAuthStatus).mockResolvedValue({
      logged_in: true,
      email: "user@example.com",
      org_name: null,
      subscription_type: null,
      auth_method: null,
    });
    const { onClose } = renderComponent();
    await waitFor(() => {
      expect(onClose).toHaveBeenCalled();
    });
  });

  it("shows error and retry button on failure", async () => {
    vi.mocked(authApi.startAuthLogin).mockRejectedValue(
      new Error("Network error"),
    );
    vi.mocked(authApi.getAuthStatus).mockResolvedValue({
      logged_in: false,
      email: null,
      org_name: null,
      subscription_type: null,
      auth_method: null,
    });
    renderComponent();
    expect(await screen.findByText("Network error")).toBeInTheDocument();
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("calls onClose when Cancel is clicked", async () => {
    vi.mocked(authApi.startAuthLogin).mockReturnValue(new Promise(() => {}));
    vi.mocked(authApi.getAuthStatus).mockResolvedValue({
      logged_in: false,
      email: null,
      org_name: null,
      subscription_type: null,
      auth_method: null,
    });
    const { onClose } = renderComponent();
    fireEvent.click(screen.getByText("Cancel"));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
