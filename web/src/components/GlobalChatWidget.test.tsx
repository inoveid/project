import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { GlobalChatWidget } from "./GlobalChatWidget";
import * as useSystemAgentModule from "../hooks/useSystemAgent";
import * as useAuthModule from "../hooks/useAuth";

vi.mock("../hooks/useSystemAgent");
vi.mock("../hooks/useAuth");
vi.mock("../hooks/chat", () => ({
  useChat: () => ({
    items: [],
    messages: [],
    status: "idle",
    error: null,
    pendingApproval: null,
    sendMessage: vi.fn(),
    stopAgent: vi.fn(),
    approveHandoff: vi.fn(),
    rejectHandoff: vi.fn(),
  }),
}));
vi.mock("../api/sessions");

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, enabled: false } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("GlobalChatWidget", () => {
  it("renders disabled button when not authenticated", () => {
    vi.mocked(useAuthModule.useAuthStatus).mockReturnValue({
      data: { logged_in: false, email: null, org_name: null, subscription_type: null, auth_method: null },
      isLoading: false,
    } as ReturnType<typeof useAuthModule.useAuthStatus>);
    vi.mocked(useSystemAgentModule.useSystemAgent).mockReturnValue({
      sessionId: null,
      isReady: false,
      resetSession: vi.fn(),
    });

    render(<GlobalChatWidget />, { wrapper: createWrapper() });

    const btn = screen.getByRole("button", { name: /авторизация/i });
    expect(btn).toBeDisabled();
  });

  it("renders toggle button when authenticated", () => {
    vi.mocked(useAuthModule.useAuthStatus).mockReturnValue({
      data: { logged_in: true, email: "u@example.com", org_name: null, subscription_type: null, auth_method: null },
      isLoading: false,
    } as ReturnType<typeof useAuthModule.useAuthStatus>);
    vi.mocked(useSystemAgentModule.useSystemAgent).mockReturnValue({
      sessionId: "session-1",
      isReady: true,
      resetSession: vi.fn(),
    });

    render(<GlobalChatWidget />, { wrapper: createWrapper() });

    expect(screen.getByRole("button", { name: /открыть чат/i })).toBeInTheDocument();
  });

  it("opens chat window on button click", async () => {
    vi.mocked(useAuthModule.useAuthStatus).mockReturnValue({
      data: { logged_in: true, email: "u@example.com", org_name: null, subscription_type: null, auth_method: null },
      isLoading: false,
    } as ReturnType<typeof useAuthModule.useAuthStatus>);
    vi.mocked(useSystemAgentModule.useSystemAgent).mockReturnValue({
      sessionId: "session-1",
      isReady: true,
      resetSession: vi.fn(),
    });

    render(<GlobalChatWidget />, { wrapper: createWrapper() });

    await userEvent.click(screen.getByRole("button", { name: /открыть чат/i }));

    expect(screen.getByText("Assistant")).toBeInTheDocument();
  });
});
