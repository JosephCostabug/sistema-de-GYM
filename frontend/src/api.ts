export class ApiError extends Error {
  readonly status: number;
  readonly fieldErrors: Record<string, string>;

  constructor(
    message: string,
    status: number,
    fieldErrors: Record<string, string> = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

const apiUrl = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000")
  .trim()
  .replace(/\/+$/, "");

interface ValidationErrorItem {
  loc?: Array<string | number>;
  msg: string;
}

function isValidationErrorItem(item: unknown): item is ValidationErrorItem {
  if (typeof item !== "object" || item === null || !("msg" in item)) return false;
  return (
    typeof item.msg === "string" &&
    (!("loc" in item) ||
      item.loc === undefined ||
      (Array.isArray(item.loc) &&
        item.loc.every((part) => typeof part === "string" || typeof part === "number")))
  );
}

function validationErrors(detail: unknown): Record<string, string> {
  if (!Array.isArray(detail)) return {};
  return Object.fromEntries(
    detail.filter(isValidationErrorItem).map((item) => {
        const field = item.loc?.at(-1);
        return [typeof field === "string" ? field : "form", item.msg];
      }),
  );
}

function apiMessage(status: number, detail: unknown): string {
  if (status === 401) return "Email ou palavra-passe inválidos.";
  if (status === 403 && typeof detail !== "string") {
    return "Não tem autorização para esta operação.";
  }
  if (status === 404) return "O recurso não foi encontrado.";
  if (status === 422 && Array.isArray(detail)) {
    const messages = detail
      .filter(isValidationErrorItem)
      .map((item) => item.msg)
      .filter(Boolean);
    if (messages.length) return messages.join(" ");
  }
  if (status === 429) return "Demasiadas tentativas. Aguarde antes de tentar novamente.";
  if (status === 503) return "O serviço está temporariamente indisponível. Tente novamente.";
  if (typeof detail === "string" && detail.trim()) return detail;
  if (status === 0) return "Sem ligação à API. Verifique a ligação e tente novamente.";
  return `Não foi possível concluir a operação (HTTP ${status}).`;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit & { token?: string } = {},
): Promise<T> {
  const { token, headers: suppliedHeaders, ...request } = options;
  const headers = new Headers(suppliedHeaders);
  if (request.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("X-Admin-Token", token);

  let response: Response;
  try {
    response = await fetch(`${apiUrl}${path}`, { ...request, headers });
  } catch {
    throw new ApiError(apiMessage(0, undefined), 0);
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = undefined;
  }

  if (!response.ok) {
    const detail =
      typeof body === "object" && body !== null && "detail" in body
        ? body.detail
        : undefined;
    throw new ApiError(
      apiMessage(response.status, detail),
      response.status,
      validationErrors(detail),
    );
  }

  if (body === undefined) {
    throw new ApiError(
      "A API devolveu uma resposta inválida. Tente novamente.",
      response.status,
    );
  }
  return body as T;
}
