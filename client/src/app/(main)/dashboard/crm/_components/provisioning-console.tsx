"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, ChevronsUpDown, Pencil, Plus, Search, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

interface Plan {
  id: number;
  name: string;
  download_speed: number;
  upload_speed: number;
  download_burst: number;
  upload_burst: number;
  price: string;
  is_active: boolean;
}

interface Customer {
  id: number;
  name: string;
  email: string | null;
  phone: string | null;
  street: string | null;
  city: string | null;
  zip_code: string | null;
  state: string | null;
}

interface Router {
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

interface Service {
  id: number;
  customer_id: number;
  plan_id: number;
  customer_name: string;
  plan_name: string;
  circuit_id: string;
  remote_id: string;
  status: "ACTIVE" | "SUSPENDED" | "TERMINATED";
}

type DeleteTarget =
  | { type: "plan"; id: number; label: string }
  | { type: "customer"; id: number; label: string }
  | { type: "service"; id: number; label: string };

const statusBadgeVariant: Record<Service["status"], "default" | "secondary" | "destructive"> = {
  ACTIVE: "default",
  SUSPENDED: "secondary",
  TERMINATED: "destructive",
};

function parseErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== "object") return fallback;
  const maybe = payload as { detail?: unknown; error?: unknown; message?: unknown };
  if (typeof maybe.detail === "string") return maybe.detail;
  if (typeof maybe.error === "string") return maybe.error;
  if (typeof maybe.message === "string") return maybe.message;
  return fallback;
}

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
  const [servicePortOptions, setServicePortOptions] = useState<string[]>([]);
  const [selectedPortName, setSelectedPortName] = useState("");
  const [selectedRouterForService, setSelectedRouterForService] = useState("");
  const [routerPortDetails, setRouterPortDetails] = useState<{
    totalPorts: number;
    occupiedPorts: number;
    availablePorts: string[];
  } | null>(null);
  const [loadingRouterPorts, setLoadingRouterPorts] = useState(false);
  const [serviceForm, setServiceForm] = useState({
    customer_id: "",
    plan_id: "",
    circuit_id: "",
    remote_id: "",
    status: "ACTIVE" as Service["status"],
  });
  const [routerSearchOpen, setRouterSearchOpen] = useState(false);
  const [selectedRouterName, setSelectedRouterName] = useState("");

  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);
  const [deleting, setDeleting] = useState(false);

  const buildCircuitIdFromPort = useCallback((portName: string): string => {
    if (!portName.startsWith("eth")) return "";
    const idx = Number.parseInt(portName.replace("eth", ""), 10);
    if (!Number.isFinite(idx) || idx <= 0) return "";
    return `1/0/${idx}`;
  }, []);

  const circuitIdToPort = useCallback((circuitId: string): string => {
    const parts = String(circuitId).split("/");
    if (parts.length !== 3) return "";
    if (parts[0] !== "1" || parts[1] !== "0") return "";
    if (!/^\d+$/.test(parts[2])) return "";
    return `eth${Number.parseInt(parts[2], 10)}`;
  }, []);

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

      const response = await fetch(
        planEdit ? `/api/plans/${planEdit.id}` : "/api/plans",
        {
          method: planEdit ? "PUT" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );

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

      const response = await fetch(
        customerEdit ? `/api/customers/${customerEdit.id}` : "/api/customers",
        {
          method: customerEdit ? "PUT" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );

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

  const fetchRouterPortDetails = useCallback(async (routerName: string, serviceId?: number) => {
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

      // Get router info for total ports
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
  }, [routers]);

  const openCreateService = () => {
    setServiceEdit(null);
    setSelectedRouterName("");
    setSelectedRouterForService("");
    setSelectedPortName("");
    setServicePortOptions([]);
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

    setSelectedRouterName(routerName);
    setSelectedRouterForService(routerName);
    setSelectedPortName(portName);
    setServiceForm({
      customer_id: String(service.customer_id),
      plan_id: String(service.plan_id),
      circuit_id: service.circuit_id,
      remote_id: service.remote_id,
      status: service.status,
    });
    
    // Fetch port details for the router
    await fetchRouterPortDetails(routerName, service.id);
    setServiceDialogOpen(true);
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

      const response = await fetch(
        serviceEdit ? `/api/services/${serviceEdit.id}` : "/api/services",
        {
          method: serviceEdit ? "PUT" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );

      const result = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(parseErrorMessage(result, "Failed to save service"));
      }

      toast.success(serviceEdit ? "Service updated" : "Service created");
      setServiceDialogOpen(false);

      // If status changed to SUSPENDED or TERMINATED, offer CoA disconnect
      const oldStatus = serviceEdit?.status;
      const newStatus = serviceForm.status;
      if (
        serviceEdit &&
        oldStatus === "ACTIVE" &&
        (newStatus === "SUSPENDED" || newStatus === "TERMINATED")
      ) {
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
          <Card>
            <CardHeader className="pb-3">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="relative w-full sm:max-w-sm">
                  <Search className="text-muted-foreground absolute top-2.5 left-2.5 h-4 w-4" />
                  <Input
                    placeholder="Search plans"
                    value={planQuery}
                    onChange={(e) => setPlanQuery(e.target.value)}
                    className="pl-8"
                  />
                </div>
                <Button onClick={openCreatePlan}>
                  <Plus className="mr-1 h-4 w-4" />
                  New Plan
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Download</TableHead>
                    <TableHead>Upload</TableHead>
                    <TableHead>Download Burst</TableHead>
                    <TableHead>Upload Burst</TableHead>
                    <TableHead>Price</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableRow>
                      <TableCell colSpan={8} className="text-muted-foreground py-6 text-center">
                        Loading plans...
                      </TableCell>
                    </TableRow>
                  ) : filteredPlans.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={8} className="text-muted-foreground py-6 text-center">
                        No plans found
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredPlans.map((plan) => (
                      <TableRow key={plan.id}>
                        <TableCell className="font-medium">{plan.name}</TableCell>
                        <TableCell>{plan.download_speed} kbps</TableCell>
                        <TableCell>{plan.upload_speed} kbps</TableCell>
                        <TableCell>{plan.download_burst} kbit</TableCell>
                        <TableCell>{plan.upload_burst} kbit</TableCell>
                        <TableCell>${Number(plan.price).toFixed(2)}</TableCell>
                        <TableCell>
                          <Badge variant={plan.is_active ? "default" : "secondary"}>
                            {plan.is_active ? "Active" : "Inactive"}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-2">
                            <Button variant="outline" size="sm" onClick={() => openEditPlan(plan)}>
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setDeleteTarget({ type: "plan", id: plan.id, label: plan.name })}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="customers" className="mt-4">
          <Card>
            <CardHeader className="pb-3">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="relative w-full sm:max-w-sm">
                  <Search className="text-muted-foreground absolute top-2.5 left-2.5 h-4 w-4" />
                  <Input
                    placeholder="Search customers"
                    value={customerQuery}
                    onChange={(e) => setCustomerQuery(e.target.value)}
                    className="pl-8"
                  />
                </div>
                <Button onClick={openCreateCustomer}>
                  <Plus className="mr-1 h-4 w-4" />
                  New Customer
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Phone</TableHead>
                    <TableHead>Location</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-muted-foreground py-6 text-center">
                        Loading customers...
                      </TableCell>
                    </TableRow>
                  ) : filteredCustomers.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-muted-foreground py-6 text-center">
                        No customers found
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredCustomers.map((customer) => (
                      <TableRow key={customer.id}>
                        <TableCell className="font-medium">{customer.name}</TableCell>
                        <TableCell>{customer.email || "-"}</TableCell>
                        <TableCell>{customer.phone || "-"}</TableCell>
                        <TableCell>{[customer.city, customer.state].filter(Boolean).join(", ") || "-"}</TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-2">
                            <Button variant="outline" size="sm" onClick={() => openEditCustomer(customer)}>
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() =>
                                setDeleteTarget({ type: "customer", id: customer.id, label: customer.name })
                              }
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="services" className="mt-4">
          <Card>
            <CardHeader className="pb-3">
              <div className="flex flex-col gap-3">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="relative w-full sm:max-w-sm">
                    <Search className="text-muted-foreground absolute top-2.5 left-2.5 h-4 w-4" />
                    <Input
                      placeholder="Search services"
                      value={serviceQuery}
                      onChange={(e) => setServiceQuery(e.target.value)}
                      className="pl-8"
                    />
                  </div>
                  <Button onClick={openCreateService} disabled={plans.length === 0 || customers.length === 0}>
                    <Plus className="mr-1 h-4 w-4" />
                    New Service
                  </Button>
                </div>
                <div className="w-full sm:max-w-55">
                  <Select
                    value={serviceStatusFilter}
                    onValueChange={(value: "ALL" | Service["status"]) => setServiceStatusFilter(value)}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Filter by status" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="ALL">All statuses</SelectItem>
                      <SelectItem value="ACTIVE">Active</SelectItem>
                      <SelectItem value="SUSPENDED">Suspended</SelectItem>
                      <SelectItem value="TERMINATED">Terminated</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {plans.length === 0 || customers.length === 0 ? (
                <p className="text-muted-foreground rounded-lg border border-dashed p-4 text-sm">
                  Create at least one plan and one customer before creating services.
                </p>
              ) : null}
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Customer</TableHead>
                    <TableHead>Plan</TableHead>
                    <TableHead>Circuit ID</TableHead>
                    <TableHead>Remote ID</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-muted-foreground py-6 text-center">
                        Loading services...
                      </TableCell>
                    </TableRow>
                  ) : filteredServices.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-muted-foreground py-6 text-center">
                        No services found
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredServices.map((service) => (
                      <TableRow key={service.id}>
                        <TableCell className="font-medium">{service.customer_name}</TableCell>
                        <TableCell>{service.plan_name}</TableCell>
                        <TableCell>{service.circuit_id}</TableCell>
                        <TableCell>{service.remote_id}</TableCell>
                        <TableCell>
                          <Badge variant={statusBadgeVariant[service.status]}>{service.status}</Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-2">
                            <Button variant="outline" size="sm" onClick={() => openEditService(service)}>
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() =>
                                setDeleteTarget({
                                  type: "service",
                                  id: service.id,
                                  label: `${service.customer_name} • ${service.circuit_id}`,
                                })
                              }
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={planDialogOpen} onOpenChange={setPlanDialogOpen}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>{planEdit ? "Edit plan" : "Create plan"}</DialogTitle>
            <DialogDescription>Speed values are in kbps and burst values are in kbit.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="plan-name">Name</Label>
              <Input id="plan-name" value={planForm.name} onChange={(e) => setPlanForm((s) => ({ ...s, name: e.target.value }))} />
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="plan-download">Download (kbps)</Label>
                <Input
                  id="plan-download"
                  type="number"
                  min="1"
                  value={planForm.download_speed}
                  onChange={(e) => setPlanForm((s) => ({ ...s, download_speed: e.target.value }))}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="plan-upload">Upload (kbps)</Label>
                <Input
                  id="plan-upload"
                  type="number"
                  min="1"
                  value={planForm.upload_speed}
                  onChange={(e) => setPlanForm((s) => ({ ...s, upload_speed: e.target.value }))}
                />
              </div>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="plan-download-burst">Download Burst (kbit)</Label>
                <Input
                  id="plan-download-burst"
                  type="number"
                  min="1"
                  value={planForm.download_burst}
                  onChange={(e) => setPlanForm((s) => ({ ...s, download_burst: e.target.value }))}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="plan-upload-burst">Upload Burst (kbit)</Label>
                <Input
                  id="plan-upload-burst"
                  type="number"
                  min="1"
                  value={planForm.upload_burst}
                  onChange={(e) => setPlanForm((s) => ({ ...s, upload_burst: e.target.value }))}
                />
              </div>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="plan-price">Price</Label>
                <Input
                  id="plan-price"
                  type="number"
                  min="0"
                  step="0.01"
                  value={planForm.price}
                  onChange={(e) => setPlanForm((s) => ({ ...s, price: e.target.value }))}
                />
              </div>
              <div className="grid gap-2">
                <Label>Status</Label>
                <Select
                  value={planForm.is_active ? "true" : "false"}
                  onValueChange={(value) => setPlanForm((s) => ({ ...s, is_active: value === "true" }))}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="true">Active</SelectItem>
                    <SelectItem value="false">Inactive</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPlanDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={savePlan} disabled={planSaving}>
              {planSaving ? "Saving..." : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={customerDialogOpen} onOpenChange={setCustomerDialogOpen}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>{customerEdit ? "Edit customer" : "Create customer"}</DialogTitle>
            <DialogDescription>Customers are OSS-side entities that can own multiple services.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="customer-name">Name</Label>
              <Input
                id="customer-name"
                value={customerForm.name}
                onChange={(e) => setCustomerForm((s) => ({ ...s, name: e.target.value }))}
              />
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="customer-email">Email</Label>
                <Input
                  id="customer-email"
                  value={customerForm.email}
                  onChange={(e) => setCustomerForm((s) => ({ ...s, email: e.target.value }))}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="customer-phone">Phone</Label>
                <Input
                  id="customer-phone"
                  value={customerForm.phone}
                  onChange={(e) => setCustomerForm((s) => ({ ...s, phone: e.target.value }))}
                />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="customer-street">Street</Label>
              <Input
                id="customer-street"
                value={customerForm.street}
                onChange={(e) => setCustomerForm((s) => ({ ...s, street: e.target.value }))}
              />
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="grid gap-2 sm:col-span-1">
                <Label htmlFor="customer-city">City</Label>
                <Input
                  id="customer-city"
                  value={customerForm.city}
                  onChange={(e) => setCustomerForm((s) => ({ ...s, city: e.target.value }))}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="customer-state">State</Label>
                <Input
                  id="customer-state"
                  value={customerForm.state}
                  onChange={(e) => setCustomerForm((s) => ({ ...s, state: e.target.value }))}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="customer-zip">ZIP</Label>
                <Input
                  id="customer-zip"
                  value={customerForm.zip_code}
                  onChange={(e) => setCustomerForm((s) => ({ ...s, zip_code: e.target.value }))}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCustomerDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={saveCustomer} disabled={customerSaving}>
              {customerSaving ? "Saving..." : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={serviceDialogOpen} onOpenChange={setServiceDialogOpen}>
        <DialogContent className="min-w-6xl">
          <DialogHeader className="pb-4">
            <div className="flex items-center justify-between">
              <DialogTitle className="text-2xl">Add a Subscriber to a Port</DialogTitle>
              <div className="flex items-center gap-2 text-sm">
                <div className="h-2.5 w-2.5 rounded-full bg-blue-500" />
                <span className="font-medium">{serviceForm.circuit_id || "1/0/3:12"}</span>
              </div>
            </div>
          </DialogHeader>
          
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Left Panel - Physical Attachment */}
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-semibold mb-4">Physical Attachment</h3>
                
                <div className="space-y-2 mb-4">
                  <Label>Access Router</Label>
                  <Select
                    value={selectedRouterForService}
                    onValueChange={async (value) => {
                      setSelectedRouterForService(value);
                      setSelectedPortName("");
                      setServiceForm((s) => ({ ...s, circuit_id: "", remote_id: value }));
                      await fetchRouterPortDetails(value, serviceEdit?.id);
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select access router" />
                    </SelectTrigger>
                    <SelectContent>
                      {routers.map((router) => (
                        <SelectItem key={router.router_name} value={router.router_name}>
                          {router.router_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-3">
                  <Label>Port</Label>
                  {loadingRouterPorts ? (
                    <div className="rounded-lg border p-4 bg-muted/30">
                      <p className="text-sm text-muted-foreground text-center py-4">Loading port information...</p>
                    </div>
                  ) : !selectedRouterForService ? (
                    <div className="rounded-lg border p-4 bg-muted/30">
                      <p className="text-sm text-muted-foreground text-center py-4">Select an access router first</p>
                    </div>
                  ) : routerPortDetails ? (
                    <div className="rounded-lg border p-4 bg-muted/30">
                      <div className="flex items-center gap-2 mb-3">
                        <span className="font-semibold text-lg">{selectedPortName || "-"}</span>
                        <div className="flex-1">
                          <div className="flex h-4 gap-0.5">
                            {Array.from({ length: routerPortDetails.totalPorts }, (_, i) => (
                              <div
                                key={i}
                                className={cn(
                                  "flex-1 rounded-sm",
                                  i < routerPortDetails.occupiedPorts ? "bg-orange-400" : "bg-gray-300"
                                )}
                              />
                            ))}
                          </div>
                          <p className="text-xs text-muted-foreground mt-1">
                            {routerPortDetails.occupiedPorts} / {routerPortDetails.totalPorts} ports used
                          </p>
                        </div>
                      </div>

                      <div className="text-sm mb-3">
                        <span className="text-muted-foreground">Available Ports</span>
                      </div>

                      <div className="grid grid-cols-8 gap-2 max-h-64 overflow-y-auto">
                        {Array.from({ length: routerPortDetails.totalPorts }, (_, i) => {
                          const portNum = i + 1;
                          const portId = `1/0/${portNum}`;
                          const portName = `eth${portNum}`;
                          const isAvailable = routerPortDetails.availablePorts.includes(portName);
                          const isSelected = serviceForm.circuit_id === portId;

                          return (
                            <button
                              key={portId}
                              onClick={() => {
                                if (isAvailable) {
                                  setSelectedPortName(portName);
                                  setServiceForm((s) => ({
                                    ...s,
                                    circuit_id: portId,
                                  }));
                                }
                              }}
                              className={cn(
                                "flex flex-col items-center justify-center aspect-square rounded-lg border-2 transition-colors p-2",
                                isSelected && "ring-2 ring-blue-500",
                                isAvailable
                                  ? "bg-teal-50 border-teal-400 hover:bg-teal-100"
                                  : "bg-red-100 border-red-400 cursor-not-allowed"
                              )}
                              disabled={!isAvailable}
                            >
                              <div
                                className={cn(
                                  "w-8 h-8 rounded flex items-center justify-center mb-1",
                                  isAvailable ? "bg-teal-200" : "bg-red-200"
                                )}
                              />
                              <span className="text-xs font-medium">{portNum}</span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ) : (
                    <div className="rounded-lg border p-4 bg-muted/30">
                      <p className="text-sm text-muted-foreground text-center py-4">Failed to load port information</p>
                    </div>
                  )}

                  <div className="flex items-center gap-4 text-sm">
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded bg-red-200 border border-red-400" />
                      <span className="text-muted-foreground">Occupied</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded bg-teal-200 border border-teal-400" />
                      <span className="text-muted-foreground">Available</span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between py-2">
                    <span className="text-sm font-medium">Port ID</span>
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-semibold">{selectedPortName ? selectedPortName.replace("eth", "") : "-"}</span>
                      <span className="text-xs text-muted-foreground">Selected Port</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Provisioning Preview */}
              <div className="rounded-lg border bg-muted/30 p-4 space-y-2">
                <h4 className="font-semibold mb-3">Provisioning Preview</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex items-start gap-2">
                    <span className="text-muted-foreground min-w-20">Circuit ID:</span>
                    <span className="font-mono font-medium">{serviceForm.circuit_id || "-"}</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="text-muted-foreground min-w-20">Remote ID:</span>
                    <span className="font-mono font-medium">{selectedRouterForService || "-"}</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="text-muted-foreground min-w-20">VLAN</span>
                    <span className="font-medium">2103</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="text-muted-foreground min-w-20">Service</span>
                    <span className="font-medium">
                      {plans.find((p) => p.id === Number(serviceForm.plan_id))?.name || "-"}
                    </span>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="text-muted-foreground min-w-20">QoS</span>
                    <span className="font-medium">gpon-res-300</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="text-muted-foreground min-w-20">AAA</span>
                    <span className="font-medium">RADIUS profile "residential-standard"</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Right Panel - Subscriber & Service Details */}
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-semibold mb-4">Subscriber & Service Details</h3>
                
                {/* Customer Search */}
                <div className="space-y-2 mb-4">
                  <Label>Search Customer</Label>
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button
                        variant="outline"
                        role="combobox"
                        className="w-full justify-between"
                      >
                        <div className="flex items-center gap-2">
                          <Search className="h-4 w-4 text-muted-foreground" />
                          <span>
                            {serviceForm.customer_id
                              ? customers.find((c) => c.id === Number(serviceForm.customer_id))?.name
                              : "Search customer..."}
                          </span>
                        </div>
                        <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-full p-0">
                      <Command>
                        <CommandInput placeholder="Search customer..." />
                        <CommandEmpty>No customer found.</CommandEmpty>
                        <CommandGroup>
                          {customers.map((customer) => (
                            <CommandItem
                              key={customer.id}
                              value={customer.name}
                              onSelect={() => {
                                setServiceForm((s) => ({ ...s, customer_id: String(customer.id) }));
                              }}
                            >
                              <Check
                                className={cn(
                                  "mr-2 h-4 w-4",
                                  serviceForm.customer_id === String(customer.id) ? "opacity-100" : "opacity-0"
                                )}
                              />
                              {customer.name}
                            </CommandItem>
                          ))}
                        </CommandGroup>
                      </Command>
                    </PopoverContent>
                  </Popover>
                </div>

                {/* Customer Details Card */}
                {serviceForm.customer_id && (() => {
                  const selectedCustomer = customers.find((c) => c.id === Number(serviceForm.customer_id));
                  return selectedCustomer ? (
                    <div className="rounded-lg border bg-card p-4 mb-6">
                      <div className="flex items-start gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 text-blue-600 font-semibold">
                          {selectedCustomer.name.charAt(0).toUpperCase()}
                        </div>
                        <div className="flex-1 space-y-1">
                          <h4 className="font-semibold">{selectedCustomer.name}</h4>
                          <p className="text-sm text-muted-foreground">A{selectedCustomer.id}</p>
                          <p className="text-sm">{selectedCustomer.street || "123 Elm St"} | {selectedCustomer.city || "Springfield"}, {selectedCustomer.state || "IL"} {selectedCustomer.zip_code || "62701"}, USA</p>
                          <p className="text-sm">{selectedCustomer.phone || "(217) 555-1234"}</p>
                          <p className="text-sm text-blue-600">{selectedCustomer.email || "john.doe@email.com"}</p>
                        </div>
                      </div>
                    </div>
                  ) : null;
                })()}

                {/* Service Profile */}
                <div className="space-y-4">
                  <h4 className="font-medium">Service Profile</h4>
                  
                  <div className="space-y-2">
                    <Label>Service Plan</Label>
                    <Select
                      value={serviceForm.plan_id}
                      onValueChange={(value) => setServiceForm((s) => ({ ...s, plan_id: value }))}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select service plan" />
                      </SelectTrigger>
                      <SelectContent>
                        {plans.filter(p => p.is_active).map((plan) => (
                          <SelectItem key={plan.id} value={String(plan.id)}>
                            {plan.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>VLAN ID</Label>
                      <Input defaultValue="2103" />
                    </div>
                    <div className="space-y-2">
                      <Label>Service VLAN</Label>
                      <Input defaultValue="2000" />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label>Status</Label>
                    <Select
                      value={serviceForm.status}
                      onValueChange={(value: Service["status"]) => setServiceForm((s) => ({ ...s, status: value }))}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="ACTIVE">Active</SelectItem>
                        <SelectItem value="SUSPENDED">Suspended</SelectItem>
                        <SelectItem value="TERMINATED">Terminated</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <DialogFooter className="mt-6">
            <Button variant="outline" onClick={() => setServiceDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={saveService} disabled={serviceSaving} className="bg-blue-600 hover:bg-blue-700">
              {serviceSaving ? "Provisioning..." : "Provision Service"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {deleteTarget?.type}</AlertDialogTitle>
            <AlertDialogDescription>
              You are about to delete <span className="font-medium">{deleteTarget?.label}</span>. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete} disabled={deleting} variant="destructive">
              {deleting ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
