import type { Service } from "./types";

export const statusBadgeVariant: Record<Service["status"], "default" | "secondary" | "destructive"> = {
  ACTIVE: "default",
  SUSPENDED: "secondary",
  TERMINATED: "destructive",
};
