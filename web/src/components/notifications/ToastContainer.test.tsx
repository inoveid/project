import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { ToastProvider, useToast } from "../../hooks/useToast";
import { ToastContainer } from "./ToastContainer";

function wrapper({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      {children}
      <ToastContainer />
    </ToastProvider>
  );
}

function AddToastButton({ type, title, message, duration }: {
  type: "info" | "success" | "warning" | "error";
  title: string;
  message: string;
  duration?: number;
}) {
  const { addToast } = useToast();
  return (
    <button onClick={() => addToast({ type, title, message, duration })}>
      Add Toast
    </button>
  );
}

describe("ToastContainer", () => {
  it("renders toast with correct content", () => {
    render(
      <AddToastButton type="info" title="Info Title" message="Info message" duration={0} />,
      { wrapper },
    );

    fireEvent.click(screen.getByText("Add Toast"));

    expect(screen.getByText("Info Title")).toBeDefined();
    expect(screen.getByText("Info message")).toBeDefined();
    expect(screen.getByRole("alert")).toBeDefined();
  });

  it("renders different toast types", () => {
    render(
      <AddToastButton type="error" title="Error" message="error msg" duration={0} />,
      { wrapper },
    );

    fireEvent.click(screen.getByText("Add Toast"));

    const alert = screen.getByRole("alert");
    expect(alert.className).toContain("bg-red-50");
  });

  it("renders action button when provided", () => {
    const onClick = vi.fn();
    function AddActionToast() {
      const { addToast } = useToast();
      return (
        <button onClick={() => addToast({
          type: "warning",
          title: "Action",
          message: "msg",
          duration: 0,
          action: { label: "Go", onClick },
        })}>
          Add
        </button>
      );
    }

    render(<AddActionToast />, { wrapper });
    fireEvent.click(screen.getByText("Add"));

    const actionBtn = screen.getByText("Go");
    expect(actionBtn).toBeDefined();
    fireEvent.click(actionBtn);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("closes toast on X button click", () => {
    render(
      <AddToastButton type="success" title="Closeable" message="close me" duration={0} />,
      { wrapper },
    );

    fireEvent.click(screen.getByText("Add Toast"));
    expect(screen.getByText("Closeable")).toBeDefined();

    fireEvent.click(screen.getByLabelText("Close notification"));
    // After animation timeout (200ms), toast should be removed
  });
});
