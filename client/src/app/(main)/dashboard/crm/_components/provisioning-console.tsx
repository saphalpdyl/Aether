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
import { ServiceDialog } from "./provisioning/service-dialog";

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

interface BNG {
  bng_id: string;
  bng_instance_id: string;
  first_seen: string;
  last_seen: string;
  is_alive: string;
  cpu_usage: number | null;
  mem_usage: number | null;
  mem_max: number | null;
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
  const [bngs, setBngs] = useState<BNG[]>([]);

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
  const [selectedBngId, setSelectedBngId] = useState("");
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
      const [plansRes, customersRes, servicesRes, routersRes, bngsRes] = await Promise.all([
        fetch("/api/plans", { cache: "no-store" }),
        fetch("/api/customers", { cache: "no-store" }),
        fetch("/api/services", { cache: "no-store" }),
        fetch("/api/routers", { cache: "no-store" }),
        fetch("/api/bngs", { cache: "no-store" }),
      ]);

      const [plansJson, customersJson, servicesJson, routersJson, bngsJson] = await Promise.all([
        plansRes.json().catch(() => ({})),
        customersRes.json().catch(() => ({})),
        servicesRes.json().catch(() => ({})),
        routersRes.json().catch(() => ({})),
        bngsRes.json().catch(() => ({})),
      ]);

      if (!plansRes.ok) throw new Error(parseErrorMessage(plansJson, "Failed to fetch plans"));
      if (!customersRes.ok) throw new Error(parseErrorMessage(customersJson, "Failed to fetch customers"));
      if (!servicesRes.ok) throw new Error(parseErrorMessage(servicesJson, "Failed to fetch services"));
      if (!routersRes.ok) throw new Error(parseErrorMessage(routersJson, "Failed to fetch routers"));
      if (!bngsRes.ok) throw new Error(parseErrorMessage(bngsJson, "Failed to fetch BNGs"));

      const plansData = Array.isArray(plansJson?.data) ? plansJson.data : [];
      const customersData = Array.isArray(customersJson?.data) ? customersJson.data : [];
      const servicesData = Array.isArray(servicesJson?.data) ? servicesJson.data : [];
      const routersData = Array.isArray(routersJson?.data) ? routersJson.data : [];
      const bngsData = Array.isArray(bngsJson?.data) ? bngsJson.data : [];

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

      setBngs(
        bngsData.map((b: any) => ({
          bng_id: String(b.bng_id ?? ""),
          bng_instance_id: String(b.bng_instance_id ?? ""),
          first_seen: String(b.first_seen ?? ""),
          last_seen: String(b.last_seen ?? ""),
          is_alive: String(b.is_alive ?? ""),
          cpu_usage: b.cpu_usage != null ? Number(b.cpu_usage) : null,
          mem_usage: b.mem_usage != null ? Number(b.mem_usage) : null,
          mem_max: b.mem_max != null ? Number(b.mem_max) : null,
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

  const filteredRouters = useMemo(() => {
    if (!selectedBngId) return [];
    return routers.filter((r) => r.bng_id === selectedBngId);
  }, [routers, selectedBngId]);

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
    setSelectedBngId("");
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

    // Find the router and set BNG
    const router = routers.find((r) => r.router_name === routerName);
    const bngId = router?.bng_id || "";
    
    setSelectedBngId(bngId);
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

  const handleBngChange = (bngId: string) => {
    setSelectedBngId(bngId);
    setSelectedRouterForService("");
    setSelectedPortName("");
    setServiceForm((s) => ({ ...s, circuit_id: "", remote_id: "" }));
    setRouterPortDetails(null);
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

      <ServiceDialog
        open={serviceDialogOpen}
        onOpenChange={setServiceDialogOpen}
        serviceEdit={serviceEdit}
        serviceForm={serviceForm}
        setServiceForm={setServiceForm}
        selectedBngId={selectedBngId}
        setSelectedBngId={setSelectedBngId}
        selectedRouterForService={selectedRouterForService}
        setSelectedRouterForService={setSelectedRouterForService}
        selectedPortName={selectedPortName}
        setSelectedPortName={setSelectedPortName}
        routerPortDetails={routerPortDetails}
        loadingRouterPorts={loadingRouterPorts}
        serviceSaving={serviceSaving}
        plans={plans}
        customers={customers}
        bngs={bngs}
        routers={routers}
        filteredRouters={filteredRouters}
        onSave={saveService}
        onBngChange={handleBngChange}
        onRouterChange={handleRouterChange}
      />

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
