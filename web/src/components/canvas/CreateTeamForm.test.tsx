import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CreateTeamForm } from "./CreateTeamForm";

describe("CreateTeamForm", () => {
  it("submits with name and description", () => {
    const onSubmit = vi.fn();
    render(<CreateTeamForm onSubmit={onSubmit} onCancel={vi.fn()} />);

    fireEvent.change(screen.getByPlaceholderText("Team name *"), { target: { value: "My Team" } });
    fireEvent.change(screen.getByPlaceholderText("Description"), { target: { value: "A team" } });
    fireEvent.click(screen.getByText("Create"));

    expect(onSubmit).toHaveBeenCalledWith({ name: "My Team", description: "A team" });
  });

  it("does not submit with empty name", () => {
    const onSubmit = vi.fn();
    render(<CreateTeamForm onSubmit={onSubmit} onCancel={vi.fn()} />);

    fireEvent.click(screen.getByText("Create"));
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("calls onCancel when Cancel clicked", () => {
    const onCancel = vi.fn();
    render(<CreateTeamForm onSubmit={vi.fn()} onCancel={onCancel} />);

    fireEvent.click(screen.getByText("Cancel"));
    expect(onCancel).toHaveBeenCalled();
  });
});
