import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SummaryCards } from "./SummaryCards";

describe("SummaryCards", () => {
  it("renders all stat cards with correct values", () => {
    render(
      <SummaryCards teamsCount={3} agentsCount={7} activeSessionsCount={2} />,
    );
    expect(screen.getByText("Teams")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Agents")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText("Active Sessions")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("renders zero values", () => {
    render(
      <SummaryCards teamsCount={0} agentsCount={0} activeSessionsCount={0} />,
    );
    const zeros = screen.getAllByText("0");
    expect(zeros).toHaveLength(3);
  });
});
