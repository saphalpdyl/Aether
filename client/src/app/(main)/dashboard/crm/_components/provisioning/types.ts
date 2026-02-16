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

export interface BNG {
  bng_id: string;
  bng_instance_id: string;
  first_seen: string;
  last_seen: string;
  is_alive: string;
  cpu_usage: number | null;
  mem_usage: number | null;
  mem_max: number | null;
}

export interface Router {
  router_name: string;
  giaddr: string;
  bng_id: string | null;
  total_interfaces: number;
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

export interface RouterPortDetails {
  totalPorts: number;
  occupiedPorts: number;
  availablePorts: string[];
}
