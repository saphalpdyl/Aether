export function parseErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== "object") return fallback;
  const maybe = payload as { detail?: unknown; error?: unknown; message?: unknown };
  if (typeof maybe.detail === "string") return maybe.detail;
  if (typeof maybe.error === "string") return maybe.error;
  if (typeof maybe.message === "string") return maybe.message;
  return fallback;
}

export function buildCircuitIdFromPort(portName: string): string {
  if (!portName.startsWith("eth")) return "";
  const idx = Number.parseInt(portName.replace("eth", ""), 10);
  if (!Number.isFinite(idx) || idx <= 0) return "";
  return `1/0/${idx}`;
}

export function circuitIdToPort(circuitId: string): string {
  const parts = String(circuitId).split("/");
  if (parts.length !== 3) return "";
  if (parts[0] !== "1" || parts[1] !== "0") return "";
  if (!/^\d+$/.test(parts[2])) return "";
  return `eth${Number.parseInt(parts[2], 10)}`;
}
