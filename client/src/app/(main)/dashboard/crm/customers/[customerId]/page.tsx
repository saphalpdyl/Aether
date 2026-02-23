"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Mail, MapPin, Phone, User, Calendar, Wifi, EthernetPort, RefreshCw, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { ServiceDialog } from "../../_components/provisioning/service-dialog";
import CustomerSessionsTable from "./_components/customer-sessions-table";
import CustomerEventsTable from "./_components/customer-events-table";
import CustomerSessionActivityChart from "./_components/customer-session-activity-chart";

interface Customer {
  id: number;
  name: string;
  email: string | null;
  phone: string | null;
  street: string | null;
  city: string | null;
  zip_code: string | null;
  state: string | null;
  created_at: string;
  updated_at: string;
}

interface Service {
  id: number;
  customer_id: number;
  plan_id: number;
  customer_name: string;
  plan_name: string;
  download_speed: number;
  upload_speed: number;
  price: string;
  circuit_id: string;
  remote_id: string;
  status: "ACTIVE" | "SUSPENDED" | "TERMINATED";
  created_at: string;
  updated_at: string;
}

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

interface RouterPortInfo {
  router_name: string;
  total_interfaces: number;
  subscriber_ports: string[];
  used_ports: string[];
  available_ports: string[];
  available_count: number;
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

function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return "—";
  
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return "—";
  
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

function formatBytes(bytes: string | null): string {
  if (!bytes) return "—";
  const value = Number(bytes);
  if (value === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(value) / Math.log(k));
  return `${(value / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
}

function formatSpeed(kbps: number): string {
  // Input is in Kbps, convert to appropriate unit
  if (kbps >= 1000000) {
    // Convert to Gbps (1000000 Kbps = 1 Gbps)
    return `${(kbps / 1000000).toFixed(1)} Gbps`;
  } else if (kbps >= 1000) {
    // Convert to Mbps (1000 Kbps = 1 Mbps)
    return `${(kbps / 1000).toFixed(1)} Mbps`;
  }
  return `${kbps} Kbps`;
}

const statusColors = {
  ACTIVE: "bg-green-500/10 text-green-700 dark:text-green-400 border-green-500/20",
  SUSPENDED: "bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/20",
  TERMINATED: "bg-gray-500/10 text-gray-700 dark:text-gray-400 border-gray-500/20",
};

function PortVisualizer({ service, portInfo }: { service: Service; portInfo: RouterPortInfo | null }) {
  if (!portInfo) {
    return <div className="text-sm text-muted-foreground">Loading port info...</div>;
  }

  const portNum = service.circuit_id.split("/")[2];
  const portName = `eth${portNum}`;
  
  return (
    <div className="rounded-lg border bg-muted/30 p-3 space-y-2">
      <div className="flex items-center gap-2">
        <div className="flex items-center justify-center w-8 h-8 rounded bg-blue-100 dark:bg-blue-900/30">
          <EthernetPort className="h-5 w-5 text-blue-600 dark:text-blue-400" />
        </div>
        <div>
          <span className="font-semibold text-sm block">{portName}</span>
          <span className="text-xs text-muted-foreground">Port {portNum}</span>
        </div>
      </div>
      
      <div className="flex h-3 gap-0.5">
        {Array.from({ length: portInfo.total_interfaces }, (_, i) => {
          const currentPortName = `eth${i + 1}`;
          const isUsed = portInfo.used_ports.includes(currentPortName);
          const isUplink = i === portInfo.total_interfaces - 1;
          const isThisService = currentPortName === portName;
          
          return (
            <div
              key={i}
              className={cn(
                "flex-1 rounded-sm transition-colors",
                isThisService
                  ? "bg-blue-500"
                  : isUplink
                  ? "bg-slate-400"
                  : isUsed
                  ? "bg-orange-400"
                  : "bg-gray-300"
              )}
              title={isThisService ? `This port (${currentPortName})` : isUplink ? "Uplink" : isUsed ? "Occupied" : "Available"}
            />
          );
        })}
      </div>
      
      <p className="text-xs text-muted-foreground">
        {portInfo.used_ports.length} / {portInfo.total_interfaces - 1} ports used on {portInfo.router_name}
      </p>
    </div>
  );
}

export default function CustomerDetailPage() {
  const params = useParams();
  const router = useRouter();
  const customerId = params?.customerId as string;

  const [loading, setLoading] = useState(true);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [services, setServices] = useState<Service[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [routerPorts, setRouterPorts] = useState<Map<string, RouterPortInfo>>(new Map());
  const [error, setError] = useState<string | null>(null);

  // Service dialog state
  const [serviceDialogOpen, setServiceDialogOpen] = useState(false);
  const [serviceEdit, setServiceEdit] = useState<Service | null>(null);
  const [serviceForm, setServiceForm] = useState<{
    customer_id: string;
    plan_id: string;
    circuit_id: string;
    remote_id: string;
    status: "ACTIVE" | "SUSPENDED" | "TERMINATED";
  }>({
    customer_id: customerId || "",
    plan_id: "",
    circuit_id: "",
    remote_id: "",
    status: "ACTIVE",
  });
  const [selectedBngId, setSelectedBngId] = useState("");
  const [selectedRouterForService, setSelectedRouterForService] = useState("");
  const [selectedPortName, setSelectedPortName] = useState("");
  const [routerPortDetails, setRouterPortDetails] = useState<{
    totalPorts: number;
    occupiedPorts: number;
    availablePorts: string[];
  } | null>(null);
  const [loadingRouterPorts, setLoadingRouterPorts] = useState(false);
  const [serviceSaving, setServiceSaving] = useState(false);
  const [bngs, setBngs] = useState<BNG[]>([]);
  const [routers, setRouters] = useState<Router[]>([]);
  const [filteredRouters, setFilteredRouters] = useState<Router[]>([]);

  // Fetch BNGs and Routers for service dialog
  const fetchBngsAndRouters = async () => {
    try {
      const [bngsRes, routersRes] = await Promise.all([
        fetch("/api/bngs"),
        fetch("/api/routers"),
      ]);

      if (bngsRes.ok) {
        const bngsData = await bngsRes.json();
        setBngs(bngsData.data || []);
      }

      if (routersRes.ok) {
        const routersData = await routersRes.json();
        setRouters(routersData.data || []);
      }
    } catch (err) {
      console.error("Error fetching BNGs and routers:", err);
    }
  };

  // Handle BNG change in service dialog
  const handleBngChange = (bngId: string) => {
    setSelectedBngId(bngId);
    const filtered = routers.filter((r) => r.bng_id === bngId);
    setFilteredRouters(filtered);
    setSelectedRouterForService("");
    setServiceForm((prev) => ({ ...prev, remote_id: "", circuit_id: "" }));
    setRouterPortDetails(null);
  };

  // Handle Router change in service dialog
  const handleRouterChange = async (routerName: string) => {
    setSelectedRouterForService(routerName);
    setServiceForm((prev) => ({ ...prev, remote_id: routerName, circuit_id: "" }));
    setSelectedPortName("");

    if (!routerName) {
      setRouterPortDetails(null);
      return;
    }

    setLoadingRouterPorts(true);
    try {
      const res = await fetch(`/api/routers/${encodeURIComponent(routerName)}/available-ports`);
      if (res.ok) {
        const data = await res.json();
        const portData = data.data;
        // Convert RouterPortInfo to RouterPortDetails format expected by dialog
        setRouterPortDetails({
          totalPorts: portData.total_interfaces,
          occupiedPorts: portData.used_ports.length,
          availablePorts: portData.available_ports,
        });
      }
    } catch (err) {
      console.error("Error fetching router ports:", err);
    } finally {
      setLoadingRouterPorts(false);
    }
  };

  // Handle service save
  const handleServiceSave = async () => {
    if (!serviceForm.plan_id || !serviceForm.circuit_id || !serviceForm.remote_id) {
      return;
    }

    setServiceSaving(true);
    try {
      const method = serviceEdit ? "PUT" : "POST";
      const url = serviceEdit ? `/api/services/${serviceEdit.id}` : "/api/services";

      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          customer_id: Number(customerId),
          plan_id: Number(serviceForm.plan_id),
          circuit_id: serviceForm.circuit_id,
          remote_id: serviceForm.remote_id,
          status: serviceForm.status,
          relay_id: selectedBngId,
        }),
      });

      if (res.ok) {
        setServiceDialogOpen(false);
        await fetchCustomerDetails(false);
      }
    } catch (err) {
      console.error("Error saving service:", err);
    } finally {
      setServiceSaving(false);
    }
  };

  // Open service dialog for adding
  const handleAddService = () => {
    setServiceEdit(null);
    setServiceForm({
      customer_id: customerId || "",
      plan_id: "",
      circuit_id: "",
      remote_id: "",
      status: "ACTIVE",
    });
    setSelectedBngId("");
    setSelectedRouterForService("");
    setSelectedPortName("");
    setRouterPortDetails(null);
    setServiceDialogOpen(true);
  };

  // Function to fetch all customer details (called on mount and manual refresh)
  const fetchCustomerDetails = async (showLoading = true) => {
    try {
      if (showLoading) {
        setLoading(true);
      }

      // Fetch customer info
      const customerRes = await fetch(`/api/customers/${customerId}`);
      if (!customerRes.ok) {
        throw new Error("Failed to fetch customer details");
      }
      const customerData = await customerRes.json();
      setCustomer(customerData.data);

      // Fetch plans first to enrich services data
      const plansRes = await fetch(`/api/plans`);
      let allPlans: Plan[] = [];
      if (plansRes.ok) {
        const plansData = await plansRes.json();
        allPlans = plansData.data || [];
      }

      // Fetch services for this customer
      const servicesRes = await fetch(`/api/services?customer_id=${customerId}`);
      let servicesData: Service[] = [];
      if (servicesRes.ok) {
        const result = await servicesRes.json();
        const rawServices = result.data || [];
        
        // Enrich services with plan data
        servicesData = rawServices.map((service: any) => {
          const plan = allPlans.find((p) => p.id === service.plan_id);
          return {
            ...service,
            download_speed: plan?.download_speed || 0,
            upload_speed: plan?.upload_speed || 0,
            price: plan?.price || service.price || "0",
          };
        });
        
        setServices(servicesData);
        
        // Fetch router port info for each service
        const uniqueRouters = new Set(servicesData.map((s: Service) => s.remote_id));
        const portPromises = Array.from(uniqueRouters).map(async (routerName) => {
          try {
            const portRes = await fetch(`/api/routers/${routerName}/available-ports`);
            if (portRes.ok) {
              const portData = await portRes.json();
              return [routerName, portData.data] as [string, RouterPortInfo];
            }
          } catch (err) {
            console.error(`Failed to fetch port info for ${routerName}:`, err);
          }
          return null;
        });
        
        const portResults = await Promise.all(portPromises);
        const portsMap = new Map<string, RouterPortInfo>();
        portResults.forEach((result) => {
          if (result) {
            portsMap.set(result[0], result[1]);
          }
        });
        setRouterPorts(portsMap);
      }

      // Set all plans (not filtered - available for adding new services)
      setPlans(allPlans);
    } catch (err) {
      console.error("Error fetching customer details:", err);
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  // Initial fetch on mount
  useEffect(() => {
    if (customerId) {
      fetchCustomerDetails();
    }
  }, [customerId]);

  // Fetch BNGs and routers when dialog opens
  useEffect(() => {
    if (serviceDialogOpen) {
      fetchBngsAndRouters();
    }
  }, [serviceDialogOpen]);

  if (loading) {
    return (
      <div className="container mx-auto p-6 space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-10 w-10" />
          <Skeleton className="h-8 w-64" />
        </div>
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-48" />
          <Skeleton className="h-48" />
          <Skeleton className="h-48" />
        </div>
      </div>
    );
  }

  if (error || !customer) {
    return (
      <div className="container mx-auto p-6">
        <Card>
          <CardHeader>
            <CardTitle>Error</CardTitle>
            <CardDescription>{error || "Customer not found"}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => router.back()}>Go Back</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">{customer.name}</h1>
            <p className="text-sm text-muted-foreground">Customer ID: {customer.id}</p>
          </div>
        </div>
        <Button 
          variant="outline" 
          size="sm"
          onClick={() => fetchCustomerDetails(false)}
          className="gap-2"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Customer Information Cards */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {/* Contact Information */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User className="h-5 w-5" />
              Contact Information
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {customer.email && (
              <div className="flex items-start gap-3">
                <Mail className="h-4 w-4 mt-0.5 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">Email</p>
                  <a href={`mailto:${customer.email}`} className="text-sm text-blue-600 dark:text-blue-400 hover:underline">
                    {customer.email}
                  </a>
                </div>
              </div>
            )}
            {customer.phone && (
              <div className="flex items-start gap-3">
                <Phone className="h-4 w-4 mt-0.5 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">Phone</p>
                  <a href={`tel:${customer.phone}`} className="text-sm text-blue-600 dark:text-blue-400 hover:underline">
                    {customer.phone}
                  </a>
                </div>
              </div>
            )}
            {(customer.street || customer.city || customer.state || customer.zip_code) && (
              <div className="flex items-start gap-3">
                <MapPin className="h-4 w-4 mt-0.5 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">Address</p>
                  <p className="text-sm text-muted-foreground">
                    {customer.street && <>{customer.street}<br /></>}
                    {[customer.city, customer.state, customer.zip_code].filter(Boolean).join(", ")}
                  </p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Account Information */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calendar className="h-5 w-5" />
              Account Information
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <p className="text-sm font-medium">Created</p>
              <p className="text-sm text-muted-foreground">{formatDate(customer.created_at)}</p>
            </div>
            <div>
              <p className="text-sm font-medium">Last Updated</p>
              <p className="text-sm text-muted-foreground">{formatDate(customer.updated_at)}</p>
            </div>
          </CardContent>
        </Card>

        {/* Quick Stats */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Wifi className="h-5 w-5" />
              Quick Stats
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between">
              <p className="text-sm font-medium">Active Services</p>
              <Badge variant="outline">{services.filter(s => s.status === "ACTIVE").length}</Badge>
            </div>
            <div className="flex justify-between">
              <p className="text-sm font-medium">Total Services</p>
              <Badge variant="outline">{services.length}</Badge>
            </div>
            <div className="flex justify-between">
              <p className="text-sm font-medium">Plans</p>
              <Badge variant="outline">{plans.length}</Badge>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Services */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Wifi className="h-5 w-5" />
                Services ({services.length})
              </CardTitle>
              <CardDescription>Active and inactive services for this customer</CardDescription>
            </div>
            <Button onClick={handleAddService} size="sm" className="gap-2">
              <Plus className="h-4 w-4" />
              Add Service
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {services.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">No services found</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Plan</TableHead>
                  <TableHead>Speed</TableHead>
                  <TableHead>Price</TableHead>
                  <TableHead>Circuit ID</TableHead>
                  <TableHead>Remote ID</TableHead>
                  <TableHead>Connected on</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {services.map((service) => (
                  <TableRow key={service.id}>
                    <TableCell className="font-medium">{service.plan_name}</TableCell>
                    <TableCell>
                      <div className="text-sm">
                        <div>↓ {formatSpeed(service.download_speed)}</div>
                        <div className="text-muted-foreground">↑ {formatSpeed(service.upload_speed)}</div>
                      </div>
                    </TableCell>
                    <TableCell>${Number(service.price).toFixed(2)}/mo</TableCell>
                    <TableCell className="font-mono text-sm">{service.circuit_id}</TableCell>
                    <TableCell className="font-mono text-sm">{service.remote_id}</TableCell>
                    <TableCell>
                      <PortVisualizer service={service} portInfo={routerPorts.get(service.remote_id) || null} />
                    </TableCell>
                    <TableCell>
                      <Badge 
                        variant="outline" 
                        className={statusColors[service.status as keyof typeof statusColors] || statusColors.TERMINATED}
                      >
                        {service.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDate(service.created_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Plans */}
      {plans.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Wifi className="h-5 w-5" />
              Available Plans ({plans.length})
            </CardTitle>
            <CardDescription>All available service plans</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Plan Name</TableHead>
                  <TableHead>Download Speed</TableHead>
                  <TableHead>Upload Speed</TableHead>
                  <TableHead>Download Burst</TableHead>
                  <TableHead>Upload Burst</TableHead>
                  <TableHead>Price</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {plans.map((plan) => (
                  <TableRow key={plan.id}>
                    <TableCell className="font-medium">{plan.name}</TableCell>
                    <TableCell>{formatSpeed(plan.download_speed)}</TableCell>
                    <TableCell>{formatSpeed(plan.upload_speed)}</TableCell>
                    <TableCell>{formatSpeed(plan.download_burst)}</TableCell>
                    <TableCell>{formatSpeed(plan.upload_burst)}</TableCell>
                    <TableCell>${Number(plan.price).toFixed(2)}/mo</TableCell>
                    <TableCell>
                      <Badge variant={plan.is_active ? "default" : "secondary"}>
                        {plan.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Session Activity Timeline */}
      <CustomerSessionActivityChart customerId={customerId} />

      {/* Active Sessions */}
      <CustomerSessionsTable customerId={customerId} />

      {/* Recent Events */}
      <CustomerEventsTable customerId={customerId} />

      {/* Service Dialog */}
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
        customers={customer ? [customer] : []}
        bngs={bngs}
        routers={routers}
        filteredRouters={filteredRouters}
        onSave={handleServiceSave}
        onBngChange={handleBngChange}
        onRouterChange={handleRouterChange}
      />
    </div>
  );
}
