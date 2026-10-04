export async function request(path, options = {}) {
  const { body, ...rest } = options;
  const multipart = body instanceof FormData;
  let response;
  try {
    response = await fetch(`/api/v1${path}`, {
      credentials: "same-origin",
      ...rest,
      headers: {
        ...(body && !multipart ? { "Content-Type": "application/json" } : {}),
        ...rest.headers,
      },
      body: body ? (multipart ? body : JSON.stringify(body)) : undefined,
    });
  } catch {
    throw new Error(
      "We couldn’t reach the server. Check your connection and try again.",
    );
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const detail =
      typeof data.detail === "string"
        ? data.detail
        : data.detail?.message || data.message;
    const error = new Error(
      detail ||
        (response.status === 401
          ? "Your session has expired. Please sign in again."
          : `The request could not be completed (${response.status}). Please try again.`),
    );
    error.status = response.status;
    throw error;
  }
  return response.status === 204 ? null : response.json();
}

export const attachmentUrl = (sessionId, id) =>
  `/api/v1/intakes/${encodeURIComponent(sessionId)}/attachments/${encodeURIComponent(id)}`;

export function dateLabel(value, time = false) {
  if (!value || Number.isNaN(new Date(value).getTime())) return "—";
  return new Intl.DateTimeFormat("en-AU", {
    day: "numeric",
    month: "short",
    year: "numeric",
    ...(time ? { hour: "numeric", minute: "2-digit" } : {}),
  }).format(new Date(value));
}

export function progressFor(session) {
  const slots = [
    ...Object.values(session?.shared_slots || {}),
    ...(session?.concerns || []).flatMap((c) => Object.values(c.slots || {})),
  ].filter((s) => s.status !== "NOT_APPLICABLE");
  const completed = slots.filter((s) =>
    ["FILLED", "SKIPPED", "UNCERTAIN"].includes(s.status),
  ).length;
  return {
    completed,
    total: slots.length,
    percent: slots.length ? Math.round((completed / slots.length) * 100) : 0,
  };
}

export function statusLabel(status) {
  return (
    {
      active: "In progress",
      review: "Ready for review",
      approved: "Shared with doctor",
      interrupted: "Safety pause",
      withdrawn: "Sharing withdrawn",
    }[status] || status
  );
}

export function fileSize(bytes = 0) {
  return bytes > 1024 * 1024
    ? `${(bytes / 1024 / 1024).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}
