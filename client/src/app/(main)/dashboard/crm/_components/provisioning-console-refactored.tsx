"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import type { Plan, Customer, Service, Router, RouterPortDetails, DeleteTarget } from "./provisioning/types";
import { parseErrorMessage, circuitIdToPort } from "./provisioning/utils";
import { PlanTab } from "./provisioning/plan-tab";
import { CustomerTab } from "./provisioning/customer-tab";
import { ServiceTab } from "./provisioning/service-tab";
import { PlanDialog } from "./provisioning/plan-dialog";
import { CustomerDialog } from "./provisioning/customer-dialog";
import { ServiceDialog } from "./provisioning/service-dialog";
import { DeleteDialog } from "./provisioning/delete-dialog";

export default function ProvisioningConsole() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [routers, setRouters] = useState<Router[]>([]);

  const [loading, setLoading] = useState(true);

  const [planQuery, setPlanQuery] = useState("");
  const [customerQuery, setCustomerQuery] = useState("");
  const [serviceQuery, setServiceQuery] = useState("");
  const [serviceStatusFilter, setServiceStatusFilter] = useState<"ALL" | Service["status"]>("ALL");

  const [planDialogOpen, setPlanDialogOpen] = useState(false);
  const [planEdit, setPlanEdit] = useState<Plan | null>(null);
  const [planSaving, setPlanSaving] = useState(false);
  const [planForm, setPlanForm] = useState({
    name: "",
    download_speed: "",
    upload_speed: "",
    download_burst: "",
    upload_burst: "",
    price: "",
    is_active: true,
  });

  const [customerDialogOpen, setCustomerDialogOpen] = useState(false);
  const [customerEdit, setCustomerEdit] = useState<Customer | null>(null);
  const [customerSaving, setCustomerSaving] = useState(false);
  const [customerForm, setCustomerForm] = useState({
    name: "",
    email: "",
    phone: "",
    street: "",
    city: "",
    zip_code: "",
    state: "",
  });

  const [serviceDialogOpen, setServiceDialogOpen] = useState(false);
  const [serviceEdit, setServiceEdit] = useState<Service | null>(null);
  const [serviceSaving, setServiceSaving] = useState(false);
  const [selectedPortName, setSelectedPortName] = useState("");
  const [selectedRouterForService, setSelectedRouterForService] = useState("");
  const [routerPortDetails, setRouterPortDetails] = useState<RouterPortDetails | null>(null);
  const [loadingRouterPorts, setLoadingRouterPorts] = useState(false);
  const [serviceForm, setServiceForm] = useState({
    customer_id: "",
    plan_id: "",
    circuit_id: "",
    remote_id: "",
    status: "ACTIVE" as Service["status"],
  });

  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);
  const [deleting, setDeleting] = useState(false);

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
          status: String(s.status ?? "ACTIVE") as Service["status"],
        }))
      );

      setRouters(
        routersData.map((r: any) => ({
          router_name: String(r.router_name ?? ""),
          giaddr: String(r.giaddr ?? ""),
          bng_id: r.bng_id ? String(r.bng_id) : null,
          total_interfaces: Number(r.total_interfaces ?? 5),
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

  const filteredPlans = useMemo(() => {
    const q = planQuery.trim().toLowerCase();
    if (!q) return plans;
    return plans.filter((p) => p.name.toLowerCase().includes(q));
  }, [plans, planQuery]);

  const filteredCustomers = useMemo(() => {
    const q = customerQuery.trim().toLowerCase();
    if (!q) return customers;
    return customers.filter((c) =>
      [c.name, c.email, c.phone, c.city, c.state]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(q))
    );
  }, [customers, customerQuery]);

  const filteredServices = useMemo(() => {
    const q = serviceQuery.trim().toLowerCase();
    return services.filter((s) => {
      const matchesStatus = serviceStatusFilter === "ALL" || s.status === serviceStatusFilter;
      const matchesQuery =
        !q ||
        [s.customer_name, s.plan_name, s.circuit_id, s.remote_id, s.status]
          .join(" ")
          .toLowerCase()
          .includes(q);
      return matchesStatus && matchesQuery;
    });
  }, [services, serviceQuery, serviceStatusFilter]);

  const openCreatePlan = () => {
    setPlanEdit(null);
    setPlanForm({
      name: "",
      download_speed: "",
      upload_speed: "",
      download_burst: "",
      upload_burst: "",
      price: "",
      is_active: true,
    });
    setPlanDialogOpen(true);
  };

  const openEditPlan = (plan: Plan) => {
    setPlanEdit(plan);
    setPlanForm({
      name: plan.name,
      download_speed: String(plan.download_speed),
      upload_speed: String(plan.upload_speed),
      download_burst: String(plan.download_burst),
      upload_burst: String(plan.upload_burst),
      price: plan.price,
      is_active: plan.is_active,
    });
    setPlanDialogOpen(true);
  };

  const savePlan = async () => {
    if (!planForm.name.trim()) {
      toast.error("Plan name is required");
      return;
    }
    if (!planForm.download_speed || Number(planForm.download_speed) <= 0) {
      toast.error("Download speed must be greater than 0");
      return;
    }
    if (!planForm.upload_speed || Number(planForm.upload_speed) <= 0) {
      toast.error("Upload speed must be greater than 0");
      return;
    }
    if (!planForm.download_burst || Number(planForm.download_burst) <= 0) {
      toast.error("Download burst must be greater than 0");
      return;
    }
    if (!planForm.upload_burst || Number(planForm.upload_burst) <= 0) {
      toast.error("Upload burst must be greater than 0");
      return;
    }
    if (!planForm.price || Number(planForm.price) < 0) {
      toast.error("Price must be 0 or greater");
      return;
    }

    setPlanSaving(true);
    try {
      const payload = {
        name: planForm.name.trim(),
        download_speed: Number(planForm.download_speed),
        upload_speed: Number(planForm.upload_speed),
        download_burst: Number(planForm.download_burst),
        upload_burst: Number(planForm.upload_burst),
        price: Number(planForm.price),
        is_active: planForm.is_active,
      };

      const response = await fetch(planEdit ? `/api/plans/${planEdit.id}` : "/api/plans", {
        method: planEdit ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const result = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(parseErrorMessage(result, "Failed to save plan"));
      }

      toast.success(planEdit ? "Plan updated" : "Plan created");
      setPlanDialogOpen(false);
      await fetchAll();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to save plan");
    } finally {
      setPlanSaving(false);
    }
  };

  const openCreateCustomer = () => {
    setCustomerEdit(null);
    setCustomerForm({ name: "", email: "", phone: "", street: "", city: "", zip_code: "", state: "" });
    setCustomerDialogOpen(true);
  };

  const openEditCustomer = (customer: Customer) => {
    setCustomerEdit(customer);
    setCustomerForm({
      name: customer.name,
      email: customer.email ?? "",
      phone: customer.phone ?? "",
      street: customer.street ?? "",
      city: customer.city ?? "",
      zip_code: customer.zip_code ?? "",
      state: customer.state ?? "",
    });
    setCustomerDialogOpen(true);
  };

  const saveCustomer = async () => {
    if (!customerForm.name.trim()) {
      toast.error("Customer name is required");
      return;
    }

    setCustomerSaving(true);
    try {
      const payload = {
        name: customerForm.name.trim(),
        email: customerForm.email.trim() || null,
        phone: customerForm.phone.trim() || null,
        street: customerForm.street.trim() || null,
        city: customerForm.city.trim() || null,
        zip_code: customerForm.zip_code.trim() || null,
        state: customerForm.state.trim() || null,
      };

      const response = await fetch(customerEdit ? `/api/customers/${customerEdit.id}` : "/api/customers", {
        method: customerEdit ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const result = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(parseErrorMessage(result, "Failed to save customer"));
      }

      toast.success(customerEdit ? "Customer updated" : "Customer created");
      setCustomerDialogOpen(false);
      await fetchAll();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to save customer");
    } finally {
      setCustomerSaving(false);
    }
  };

  const fetchRouterPortDetails = useCallback(
    async (routerName: string, serviceId?: number) => {
      if (!routerName) {
        setRouterPortDetails(null);
        return;
      }

      setLoadingRouterPorts(true);
      try {
        const qp = serviceId ? `?service_id=${serviceId}` : "";
        const response = await fetch(`/api/routers/${encodeURIComponent(routerName)}/available-ports${qp}`, {
          cache: "no-store",
        });
        const result = await response.json().catch(() => ({}));

        if (!response.ok) {
          throw new Error(parseErrorMessage(result, "Failed to fetch router port details"));
        }

        const router = routers.find((r) => r.router_name === routerName);
        const totalPorts = router?.total_interfaces || 64;
        const availablePorts = Array.isArray(result?.data?.available_ports) ? result.data.available_ports : [];
        const occupiedPorts = totalPorts - availablePorts.length;

        setRouterPortDetails({
          totalPorts,
          occupiedPorts,
          availablePorts: availablePorts.map((p: unknown) => String(p)),
        });
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to fetch router port details");
        setRouterPortDetails(null);
      } finally {
        setLoadingRouterPorts(false);
      }
    },
    [routers]
  );

  const openCreateService = () => {
    setServiceEdit(null);
    setSelectedRouterForService("");
    setSelectedPortName("");
    setRouterPortDetails(null);
    setServiceForm({
      customer_id: customers[0] ? String(customers[0].id) : "",
      plan_id: plans[0] ? String(plans[0].id) : "",
      circuit_id: "",
      remote_id: "",
      status: "ACTIVE",
    });
    setServiceDialogOpen(true);
  };

  const openEditService = async (service: Service) => {
    setServiceEdit(service);
    const routerName = service.remote_id || "";
    const portName = circuitIdToPort(service.circuit_id);

    setSelectedRouterForService(routerName);
    setSelectedPortName(portName);
    setServiceForm({
      customer_id: String(service.customer_id),
      plan_id: String(service.plan_id),
      circuit_id: service.circuit_id,
      remote_id: service.remote_id,
      status: service.status,
    });

    await fetchRouterPortDetails(routerName, service.id);
    setServiceDialogOpen(true);
  };

  const handleRouterChange = async (routerName: string) => {
    setSelectedRouterForService(routerName);
    setSelectedPortName("");
    setServiceForm((s) => ({ ...s, circuit_id: "", remote_id: routerName }));
    await fetchRouterPortDetails(routerName, serviceEdit?.id);
  };

  const saveService = async () => {
    if (!serviceForm.customer_id || !serviceForm.plan_id) {
      toast.error("Customer and plan are required");
      return;
    }
    if (!selectedRouterForService) {
      toast.error("Access router selection is required");
      return;
    }
    if (!selectedPortName || !serviceForm.circuit_id) {
      toast.error("Port selection is required");
      return;
    }

    setServiceSaving(true);
    try {
      const selectedRouter = routers.find((r) => r.router_name === selectedRouterForService);
      if (!selectedRouter?.bng_id) {
        throw new Error("Selected access router is missing bng_id");
      }

      const payload = {
        customer_id: Number(serviceForm.customer_id),
        plan_id: Number(serviceForm.plan_id),
        circuit_id: serviceForm.circuit_id,
        remote_id: selectedRouterForService,
        relay_id: selectedRouter.bng_id,
        status: serviceForm.status,
      };

      const response = await fetch(serviceEdit ? `/api/services/${serviceEdit.id}` : "/api/services", {
        method: serviceEdit ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const result = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(parseErrorMessage(result, "Failed to save service"));
      }

      toast.success(serviceEdit ? "Service updated" : "Service created");
      setServiceDialogOpen(false);

      const oldStatus = serviceEdit?.status;
      const newStatus = serviceForm.status;
      if (serviceEdit && oldStatus === "ACTIVE" && (newStatus === "SUSPENDED" || newStatus === "TERMINATED")) {
        const shouldDisconnect = confirm(
          `Service status changed to ${newStatus}.\n\nSend a CoA Disconnect to terminate the subscriber's active session now?`
        );
        if (shouldDisconnect) {
          try {
            const dcResp = await fetch(`/api/services/${serviceEdit.id}/disconnect`, {
              method: "POST",
            });
            const dcResult = await dcResp.json().catch(() => ({}));
            if (dcResp.ok && dcResult.success) {
              toast.success(`CoA Disconnect sent (${dcResult.reply_code})`);
            } else if (dcResp.status === 404) {
              toast.info("No active session found for this service");
            } else {
              toast.error(dcResult.error || dcResult.detail || "CoA Disconnect failed");
            }
          } catch {
            toast.error("Failed to send CoA Disconnect");
          }
        }
      }

      await fetchAll();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to save service");
    } finally {
      setServiceSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;

    setDeleting(true);
    try {
      const endpoint =
        deleteTarget.type === "plan"
          ? `/api/plans/${deleteTarget.id}`
          : deleteTarget.type === "customer"
            ? `/api/customers/${deleteTarget.id}`
            : `/api/services/${deleteTarget.id}`;

      const response = await fetch(endpoint, { method: "DELETE" });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(parseErrorMessage(result, "Delete failed"));
      }

      toast.success("Deleted successfully");
      setDeleteTarget(null);
      await fetchAll();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Delete failed");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="flex flex-col gap-4 md:gap-6">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle>Provisioning</CardTitle>
          <CardDescription>
            Manage plans, customers, and services in one workspace. Plan deletion is blocked while services are attached.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="rounded-lg border p-3">
            <p className="text-muted-foreground text-xs">Plans</p>
            <p className="text-2xl font-semibold">{plans.length}</p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-muted-foreground text-xs">Customers</p>
            <p className="text-2xl font-semibold">{customers.length}</p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-muted-foreground text-xs">Services</p>
            <p className="text-2xl font-semibold">{services.length}</p>
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="plans" className="w-full">
        <TabsList>
          <TabsTrigger value="plans">Plans</TabsTrigger>
          <TabsTrigger value="customers">Customers</TabsTrigger>
          <TabsTrigger value="services">Services</TabsTrigger>
        </TabsList>

        <TabsContent value="plans" className="mt-4">
          <PlanTab
            plans={plans}
            loading={loading}
            planQuery={planQuery}
            setPlanQuery={setPlanQuery}
            filteredPlans={filteredPlans}
            onCreatePlan={openCreatePlan}
            onEditPlan={openEditPlan}
            onDeletePlan={setDeleteTarget}
          />
        </TabsContent>

        <TabsContent value="customers" className="mt-4">
          <CustomerTab
            customers={customers}
            loading={loading}
            customerQuery={customerQuery}
            setCustomerQuery={setCustomerQuery}
            filteredCustomers={filteredCustomers}
            onCreateCustomer={openCreateCustomer}
            onEditCustomer={openEditCustomer}
            onDeleteCustomer={setDeleteTarget}
          />
        </TabsContent>

        <TabsContent value="services" className="mt-4">
          <ServiceTab
            services={services}
            loading={loading}
            serviceQuery={serviceQuery}
            setServiceQuery={setServiceQuery}
            serviceStatusFilter={serviceStatusFilter}
            setServiceStatusFilter={setServiceStatusFilter}
            filteredServices={filteredServices}
            plansCount={plans.length}
            customersCount={customers.length}
            onCreateService={openCreateService}
            onEditService={openEditService}
            onDeleteService={setDeleteTarget}
          />
        </TabsContent>
      </Tabs>

      <PlanDialog
        open={planDialogOpen}
        onOpenChange={setPlanDialogOpen}
        planEdit={planEdit}
        planForm={planForm}
        setPlanForm={setPlanForm}
        planSaving={planSaving}
        onSave={savePlan}
      />

      <CustomerDialog
        open={customerDialogOpen}
        onOpenChange={setCustomerDialogOpen}
        customerEdit={customerEdit}
        customerForm={customerForm}
        setCustomerForm={setCustomerForm}
        customerSaving={customerSaving}
        onSave={saveCustomer}
      />

      <ServiceDialog
        open={serviceDialogOpen}
        onOpenChange={setServiceDialogOpen}
        serviceEdit={serviceEdit}
        serviceForm={serviceForm}
        setServiceForm={setServiceForm}
        selectedRouterForService={selectedRouterForService}
        setSelectedRouterForService={setSelectedRouterForService}
        selectedPortName={selectedPortName}
        setSelectedPortName={setSelectedPortName}
        routerPortDetails={routerPortDetails}
        loadingRouterPorts={loadingRouterPorts}
        serviceSaving={serviceSaving}
        plans={plans}
        customers={customers}
        routers={routers}
        onSave={saveService}
        onRouterChange={handleRouterChange}
      />

      <DeleteDialog
        deleteTarget={deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        deleting={deleting}
        onConfirm={confirmDelete}
      />
    </div>
  );
}
