/**
 * Provisioning Console Type Definitions
 */

export interface Plan {
  id: number;
  name: string;
  download_speed: number;
  upload_speed: number;
  download_burst: number;
  upload_burst: number;
  price: string;
  is_active: boolean;
}

export interface Customer {
  id: number;
  name: string;
  email: string | null;
  phone: string | null;
  street: string | null;
  city: string | null;
  zip_code: string | null;
  state: string | null;
}

export interface Router {
  router_name: string;
  giaddr: string;
  bng_id: string | null;
  is_alive: string;
  last_seen: string | null;
  last_ping: string | null;
  active_subscribers: number;
  created_at: string;
  updated_at: string;
}

export interface Service {
  id: number;
  customer_id: number;
  plan_id: number;
  customer_name: string;
  plan_name: string;
  circuit_id: string;
  remote_id: string;
  status: "ACTIVE" | "SUSPENDED" | "TERMINATED";
}

export type DeleteTarget =
  | { type: "plan"; id: number; label: string }
  | { type: "customer"; id: number; label: string }
  | { type: "service"; id: number; label: string };

export const statusBadgeVariant: Record<Service["status"], "default" | "secondary" | "destructive"> = {
  ACTIVE: "default",
  SUSPENDED: "secondary",
  TERMINATED: "destructive",
};

export function parseErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== "object") return fallback;
  const maybe = payload as { detail?: unknown; error?: unknown; message?: unknown };
  if (typeof maybe.detail === "string") return maybe.detail;
  if (typeof maybe.error === "string") return maybe.error;
  if (typeof maybe.message === "string") return maybe.message;
  return fallback;
}

export function buildCircuitId(routerName: string, _remoteId: string): string {
  if (!routerName) return "";
  // circuit_id is just the access node identity — relay_id/remote_id are added by the backend
  return `${routerName}|default|irb1|1:0`;
}
