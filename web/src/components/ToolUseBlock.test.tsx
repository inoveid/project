import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ToolUseBlock } from "./ToolUseBlock";

const toolUse = {
  tool_name: "Read",
  tool_input: { file_path: "/src/index.ts" },
};

describe("ToolUseBlock", () => {
  it("renders tool name and preview", () => {
    render(<ToolUseBlock toolUse={toolUse} />);
    expect(screen.getByText("Read")).toBeInTheDocument();
    expect(screen.getByText(/file_path/)).toBeInTheDocument();
  });

  it("is collapsed by default (no expanded JSON)", () => {
    const { container } = render(<ToolUseBlock toolUse={toolUse} />);
    expect(container.querySelector("pre")).toBeNull();
  });

  it("expands on click to show full JSON", async () => {
    const user = userEvent.setup();
    render(<ToolUseBlock toolUse={toolUse} />);
    await user.click(screen.getByRole("button"));
    expect(screen.getByText(/\/src\/index\.ts/)).toBeInTheDocument();
  });
});
