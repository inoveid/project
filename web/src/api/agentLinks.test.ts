import { describe, expect, it, vi, beforeEach } from "vitest";
import { getAgentLinks, createAgentLink, deleteAgentLink } from "./agentLinks";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

function jsonResponse(data: unknown, status = 200) {
  return {
    ok: true,
    status,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  };
}

function emptyResponse() {
  return {
    ok: true,
    status: 204,
    json: () => Promise.resolve(undefined),
    text: () => Promise.resolve(""),
  };
}

function errorResponse(status: number, body: string) {
  return {
    ok: false,
    status,
    json: () => Promise.resolve({ detail: body }),
    text: () => Promise.resolve(body),
  };
}

beforeEach(() => {
  mockFetch.mockReset();
});

describe("getAgentLinks", () => {
  it("fetches links for a team", async () => {
    const links = [{ id: "link-1", link_type: "handoff" }];
    mockFetch.mockResolvedValue(jsonResponse(links));
    const result = await getAgentLinks("team-1");
    expect(result).toEqual(links);
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/teams/team-1/links",
      expect.objectContaining({ headers: expect.any(Object) }),
    );
  });
});

describe("createAgentLink", () => {
  it("posts a new link", async () => {
    const link = { id: "link-1", link_type: "handoff" };
    mockFetch.mockResolvedValue(jsonResponse(link, 201));
    const result = await createAgentLink("team-1", {
      from_agent_id: "a1",
      to_agent_id: "a2",
      link_type: "handoff",
    });
    expect(result).toEqual(link);
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/teams/team-1/links",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("throws on error response", async () => {
    mockFetch.mockResolvedValue(errorResponse(409, "duplicate"));
    await expect(
      createAgentLink("team-1", {
        from_agent_id: "a1",
        to_agent_id: "a2",
        link_type: "handoff",
      }),
    ).rejects.toThrow("API error 409");
  });
});

describe("deleteAgentLink", () => {
  it("sends delete request", async () => {
    mockFetch.mockResolvedValue(emptyResponse());
    await deleteAgentLink("link-1");
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/links/link-1",
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});
