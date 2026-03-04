import { describe, expect, it, vi, beforeEach } from "vitest";
import { createSession, getSessions, getSession, stopSession } from "./sessions";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch as typeof fetch;

function jsonResponse(data: unknown, status = 200) {
  return {
    ok: true,
    status,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  };
}

function emptyResponse() {
  return { ok: true, status: 204, json: () => Promise.resolve(undefined), text: () => Promise.resolve("") };
}

beforeEach(() => {
  mockFetch.mockReset();
});

describe("sessions API", () => {
  it("createSession sends POST with agent_id", async () => {
    const session = { id: "s-1", agent_id: "a-1", status: "active" };
    mockFetch.mockResolvedValueOnce(jsonResponse(session));

    const result = await createSession("a-1");
    expect(result).toEqual(session);
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/sessions",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("getSessions fetches list", async () => {
    const list = [{ id: "s-1" }];
    mockFetch.mockResolvedValueOnce(jsonResponse(list));

    const result = await getSessions();
    expect(result).toEqual(list);
  });

  it("getSession fetches by id", async () => {
    const session = { id: "s-1", messages: [] };
    mockFetch.mockResolvedValueOnce(jsonResponse(session));

    const result = await getSession("s-1");
    expect(result).toEqual(session);
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/sessions/s-1",
      expect.anything(),
    );
  });

  it("stopSession sends DELETE", async () => {
    mockFetch.mockResolvedValueOnce(emptyResponse());

    await stopSession("s-1");
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/sessions/s-1",
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});
