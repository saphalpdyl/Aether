/**
 * Custom hooks for provisioning data management
 */

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import type { Customer, Plan, Router, Service } from "./provisioning-types";
import { parseErrorMessage } from "./provisioning-types";

interface ProvisioningData {
  plans: Plan[];
  customers: Customer[];
  services: Service[];
  routers: Router[];
  loading: boolean;
  fetchAll: () => Promise<void>;
}

export function useProvisioningData(): ProvisioningData {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [routers, setRouters] = useState<Router[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [plansRes, customersRes, servicesRes, routersRes] = await Promise.all([
        fetch("/api/plans", { cache: "no-store" }),
        fetch("/api/customers", { cache: "no-store" }),
        fetch("/api/services", { cache: "no-store" }),
        fetch("/api/routers", { cache: "no-store" }),
      ]);

      const [plansJson, customersJson, servicesJson, routersJson] = await Promise.all([
        plansRes.json().catch(() => ({})),
        customersRes.json().catch(() => ({})),
        servicesRes.json().catch(() => ({})),
        routersRes.json().catch(() => ({})),
      ]);

      if (!plansRes.ok) throw new Error(parseErrorMessage(plansJson, "Failed to fetch plans"));
      if (!customersRes.ok) throw new Error(parseErrorMessage(customersJson, "Failed to fetch customers"));
      if (!servicesRes.ok) throw new Error(parseErrorMessage(servicesJson, "Failed to fetch services"));
      if (!routersRes.ok) throw new Error(parseErrorMessage(routersJson, "Failed to fetch routers"));

      const plansData = Array.isArray(plansJson?.data) ? plansJson.data : [];
      const customersData = Array.isArray(customersJson?.data) ? customersJson.data : [];
      const servicesData = Array.isArray(servicesJson?.data) ? servicesJson.data : [];
      const routersData = Array.isArray(routersJson?.data) ? routersJson.data : [];

      setPlans(
        plansData.map((p: any) => ({
          id: Number(p.id),
          name: String(p.name ?? ""),
          download_speed: Number(p.download_speed ?? 0),
          upload_speed: Number(p.upload_speed ?? 0),
          download_burst: Number(p.download_burst ?? 0),
          upload_burst: Number(p.upload_burst ?? 0),
          price: String(p.price ?? "0.00"),
          is_active: String(p.is_active) === "True",
        }))
      );

      setCustomers(
        customersData.map((c: any) => ({
          id: Number(c.id),
          name: String(c.name ?? ""),
          email: c.email ? String(c.email) : null,
          phone: c.phone ? String(c.phone) : null,
          street: c.street ? String(c.street) : null,
          city: c.city ? String(c.city) : null,
          zip_code: c.zip_code ? String(c.zip_code) : null,
          state: c.state ? String(c.state) : null,
        }))
      );

      setServices(
        servicesData.map((s: any) => ({
          id: Number(s.id),
          customer_id: Number(s.customer_id),
          plan_id: Number(s.plan_id),
          customer_name: String(s.customer_name ?? ""),
          plan_name: String(s.plan_name ?? ""),
          circuit_id: String(s.circuit_id ?? ""),
          remote_id: String(s.remote_id ?? ""),
          status: (String(s.status ?? "ACTIVE") as Service["status"]),
        }))
      );

      setRouters(
        routersData.map((r: any) => ({
          router_name: String(r.router_name ?? ""),
          giaddr: String(r.giaddr ?? ""),
          bng_id: r.bng_id ? String(r.bng_id) : null,
          is_alive: String(r.is_alive ?? ""),
          last_seen: r.last_seen ? String(r.last_seen) : null,
          last_ping: r.last_ping ? String(r.last_ping) : null,
          active_subscribers: Number(r.active_subscribers ?? 0),
          created_at: String(r.created_at ?? ""),
          updated_at: String(r.updated_at ?? ""),
        }))
      );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to load provisioning data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  return { plans, customers, services, routers, loading, fetchAll };
}
