import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, hasToken, setToken } from "./api";

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockReset();
  setToken(null);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

/** The URL and init of call `n`, with the index-access narrowing done once. */
function callArgs(n = 0): { url: string; init: RequestInit } {
  const call = fetchMock.mock.calls[n];
  if (!call) throw new Error(`fetch was not called ${n + 1} time(s)`);
  return { url: call[0] as string, init: (call[1] ?? {}) as RequestInit };
}

function ok(body: unknown) {
  return Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve(body),
  });
}

describe("token handling", () => {
  it("is not held before sign-in", () => {
    expect(hasToken()).toBe(false);
  });

  it("sends the token as a bearer credential", async () => {
    setToken("secret-token");
    fetchMock.mockReturnValue(ok({}));

    await api.me();

    const headers = callArgs().init.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer secret-token");
  });

  it("sends no credential when signed out", async () => {
    fetchMock.mockReturnValue(ok({}));

    await api.me();

    const headers = callArgs().init.headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
  });

  it("never writes the token to storage", async () => {
    // A token in localStorage is readable by any injected script, and this one
    // reaches patient transcripts.
    setToken("secret-token");
    fetchMock.mockReturnValue(ok({}));

    await api.me();

    expect(localStorage.getItem("token")).toBeNull();
    expect(JSON.stringify(localStorage)).not.toContain("secret-token");
    expect(JSON.stringify(sessionStorage)).not.toContain("secret-token");
  });
});

describe("tenant scoping", () => {
  it("omits the tenant parameter when none is given", async () => {
    fetchMock.mockReturnValue(ok([]));
    await api.calls(null);
    expect(callArgs().url).toBe("/api/calls?limit=50");
  });

  it("appends the tenant when one is given", async () => {
    fetchMock.mockReturnValue(ok([]));
    await api.calls("northside");
    expect(callArgs().url).toContain("tenant=northside");
  });

  it("encodes a tenant id rather than interpolating it raw", async () => {
    fetchMock.mockReturnValue(ok([]));
    await api.calls("a b&c=d");
    expect(callArgs().url).toContain("tenant=a%20b%26c%3Dd");
  });

  it("encodes a call id in the path", async () => {
    fetchMock.mockReturnValue(ok({}));
    await api.call("../../secrets");
    expect(callArgs().url).toBe("/api/calls/..%2F..%2Fsecrets");
  });
});

describe("errors", () => {
  it("raises ApiError carrying the status", async () => {
    fetchMock.mockReturnValue(
      Promise.resolve({
        ok: false,
        status: 403,
        statusText: "Forbidden",
        json: () => Promise.resolve({ detail: "not your clinic" }),
      }),
    );

    await expect(api.calls("other")).rejects.toThrowError(ApiError);
    await expect(api.calls("other")).rejects.toMatchObject({
      status: 403,
      message: "not your clinic",
    });
  });

  it("survives a non-JSON error body", async () => {
    fetchMock.mockReturnValue(
      Promise.resolve({
        ok: false,
        status: 502,
        statusText: "Bad Gateway",
        json: () => Promise.reject(new Error("not json")),
      }),
    );

    await expect(api.me()).rejects.toMatchObject({ status: 502 });
  });
});
