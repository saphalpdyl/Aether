"use client";

import { Check, ChevronsUpDown, Search, Cable, EthernetPort } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
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
import type { Service, Plan, Customer, Router, RouterPortDetails, BNG } from "./types";

interface ServiceDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  serviceEdit: Service | null;
  serviceForm: {
    customer_id: string;
    plan_id: string;
    circuit_id: string;
    remote_id: string;
    status: Service["status"];
  };
  setServiceForm: React.Dispatch<React.SetStateAction<{
    customer_id: string;
    plan_id: string;
    circuit_id: string;
    remote_id: string;
    status: Service["status"];
  }>>;
  selectedBngId: string;
  setSelectedBngId: (bngId: string) => void;
  selectedRouterForService: string;
  setSelectedRouterForService: (router: string) => void;
  selectedPortName: string;
  setSelectedPortName: (port: string) => void;
  routerPortDetails: RouterPortDetails | null;
  loadingRouterPorts: boolean;
  serviceSaving: boolean;
  plans: Plan[];
  customers: Customer[];
  bngs: BNG[];
  routers: Router[];
  filteredRouters: Router[];
  onSave: () => void;
  onBngChange: (bngId: string) => void;
  onRouterChange: (routerName: string) => void;
}

export function ServiceDialog({
  open,
  onOpenChange,
  serviceEdit,
  serviceForm,
  setServiceForm,
  selectedBngId,
  setSelectedBngId,
  selectedRouterForService,
  setSelectedRouterForService,
  selectedPortName,
  setSelectedPortName,
  routerPortDetails,
  loadingRouterPorts,
  serviceSaving,
  plans,
  customers,
  bngs,
  routers,
  filteredRouters,
  onSave,
  onBngChange,
  onRouterChange,
}: ServiceDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
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
                <Label>BNG</Label>
                <Select
                  value={selectedBngId}
                  onValueChange={onBngChange}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select BNG" />
                  </SelectTrigger>
                  <SelectContent>
                    {bngs.map((bng) => (
                      <SelectItem key={bng.bng_id} value={bng.bng_id}>
                        {bng.bng_id}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2 mb-4">
                <Label>Access Router</Label>
                <Select
                  value={selectedRouterForService}
                  onValueChange={onRouterChange}
                  disabled={!selectedBngId}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={selectedBngId ? "Select access router" : "Select BNG first"} />
                  </SelectTrigger>
                  <SelectContent>
                    {filteredRouters.map((router) => (
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
                        const isUplink = portNum === routerPortDetails.totalPorts; // Last port is uplink

                        return (
                          <button
                            key={portId}
                            onClick={() => {
                              if (isAvailable && !isUplink) {
                                setSelectedPortName(portName);
                                setServiceForm((s) => ({
                                  ...s,
                                  circuit_id: portId,
                                }));
                              }
                            }}
                            className={cn(
                              "flex flex-col items-center justify-center aspect-square rounded-lg border-2 transition-colors p-2 cursor-pointer",
                              isUplink
                                ? "bg-slate-100 border-slate-400 cursor-not-allowed"
                                : isAvailable
                                ? isSelected
                                  ? "bg-teal-700 border-teal-700"
                                  : "bg-teal-50 border-teal-400 hover:bg-teal-100"
                                : "bg-red-100 border-red-400 cursor-not-allowed"
                            )}
                            disabled={!isAvailable || isUplink}
                            title={isUplink ? "Uplink Port (Reserved)" : isAvailable ? "Available" : "Occupied"}
                          >
                            <EthernetPort
                              className={cn(
                                "w-8 h-8",
                                isUplink 
                                  ? "text-slate-600" 
                                  : isAvailable 
                                  ? isSelected 
                                    ? "text-white" 
                                    : "text-teal-600" 
                                  : "text-red-600"
                              )}
                            />
                            <span className={cn(
                              "text-xs font-medium",
                              isSelected && isAvailable && "text-white"
                            )}>{portNum}</span>
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
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded bg-slate-300 border border-slate-400" />
                    <span className="text-muted-foreground">Uplink</span>
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
                  <span className="text-muted-foreground min-w-20">Service</span>
                  <span className="font-medium">
                    {plans.find((p) => p.id === Number(serviceForm.plan_id))?.name || "-"}
                  </span>
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
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={onSave} disabled={serviceSaving} className="bg-blue-600 hover:bg-blue-700">
            {serviceSaving ? "Provisioning..." : "Provision Service"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
