import { afterEach, describe, expect, it, vi } from "vitest";
import { apiFetch } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiFetch", () => {
  it("sends the session token in the API header and returns JSON", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      new Response(JSON.stringify({ nome: "Ginásio Central" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await apiFetch<{ nome: string }>("/empresa", { token: "session-token" });

    expect(result.nome).toBe("Ginásio Central");
    const requestHeaders = new Headers(fetchMock.mock.calls[0][1]?.headers);
    expect(requestHeaders.get("X-Admin-Token")).toBe("session-token");
  });

  it("exposes structured validation errors by field", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        detail: [{ loc: ["body", "email"], msg: "Endereço inválido." }],
      }), { status: 422 }),
    ));

    await expect(apiFetch("/admin/login", { method: "POST" })).rejects.toMatchObject({
      status: 422,
      fieldErrors: { email: "Endereço inválido." },
    });
  });

  it("uses a neutral message for unauthenticated responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Email ou senha inválidos." }), { status: 401 }),
    ));

    await expect(apiFetch("/admin/login")).rejects.toMatchObject({
      status: 401,
      message: "Email ou palavra-passe inválidos.",
    });
  });

  it("reports network failures explicitly", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(apiFetch("/empresa")).rejects.toMatchObject({
      name: "ApiError",
      status: 0,
      message: "Sem ligação à API. Verifique a ligação e tente novamente.",
    });
  });
});
