"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import { Home, Network, Bug, Info, AlertTriangle, Maximize2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import simulateEnvIll from "@/assets/illustrations/simulate_env_ill.png";

interface Service {
  id: number;
  customer_id: number;
  plan_id: number;
  customer_name: string;
  plan_name: string;
  circuit_id: string;
  remote_id: string;
  relay_id?: string;
  status: "ACTIVE" | "SUSPENDED" | "TERMINATED";
}

interface SimulateCommand {
  command: string;
  description: string;
}

interface SimulateNote {
  type: "info" | "warning";
  text: string;
}

interface SimulateOption {
  name: string;
  description: string;
  commands: SimulateCommand[];
  note?: SimulateNote;
}

interface SimulateOptionsResponse {
  count: number;
  options: SimulateOption[];
}

export function SimulateLabEnvironment() {
  const [selectedService, setSelectedService] = useState<string>("");
  const [services, setServices] = useState<Service[]>([]);
  const [loading, setLoading] = useState(true);
  const [simulateOptions, setSimulateOptions] = useState<SimulateOption[]>([]);
  const [selectedCommandGroup, setSelectedCommandGroup] = useState<string>("");
  const [selectedCommand, setSelectedCommand] = useState<string>("");
  const [simulating, setSimulating] = useState(false);
  const [output, setOutput] = useState<string>("");
  const [elapsedTime, setElapsedTime] = useState<number>(0);
  const [outputDialogOpen, setOutputDialogOpen] = useState(false);

  // Timer effect for elapsed time
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    let startTime: number;

    if (simulating) {
      startTime = Date.now();
      setElapsedTime(0);
      interval = setInterval(() => {
        setElapsedTime((Date.now() - startTime) / 1000);
      }, 10); // Update every 10ms for smooth display
    }

    return () => {
      if (interval) {
        clearInterval(interval);
      }
    };
  }, [simulating]);

  // Fetch services on component mount
  useEffect(() => {
    const fetchServices = async () => {
      try {
        setLoading(true);
        const response = await fetch("/api/services");
        if (!response.ok) {
          throw new Error("Failed to fetch services");
        }
        const data = await response.json();
        setServices(data.data || []);
      } catch (error) {
        console.error("Error fetching services:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchServices();
  }, []);

  // Fetch simulation options on component mount
  useEffect(() => {
    const fetchSimulateOptions = async () => {
      try {
        const response = await fetch("/api/simulation/get_simulate_options");
        if (!response.ok) {
          throw new Error("Failed to fetch simulation options");
        }
        const data: SimulateOptionsResponse = await response.json();
        setSimulateOptions(data.options || []);
      } catch (error) {
        console.error("Error fetching simulation options:", error);
      }
    };

    fetchSimulateOptions();
  }, []);

  // Convert services to combobox options
  const serviceOptions: ComboboxOption[] = services
    .filter((service) => service.status === "ACTIVE")
    .map((service) => ({
      value: `${service.id}|${service.customer_name} ${service.plan_name}`,
      label: `${service.customer_name} - ${service.plan_name}`,
      subtitle: `Circuit: ${service.circuit_id} | Remote: ${service.remote_id}`,
    }));

  // Convert command groups to combobox options
  const commandGroupOptions: ComboboxOption[] = simulateOptions.map((option) => ({
    value: option.name,
    label: option.name.replace(/_/g, ' ').toUpperCase(),
    subtitle: option.description,
  }));

  // Get commands for selected group
  const selectedGroup = simulateOptions.find((opt) => opt.name === selectedCommandGroup);
  const commandOptions: ComboboxOption[] = selectedGroup
    ? selectedGroup.commands.map((cmd) => ({
        value: cmd.command,
        label: cmd.description,
        subtitle: cmd.command,
      }))
    : [];

  const handleSimulate = async () => {
    if (!selectedService || !selectedCommandGroup || !selectedCommand) {
      return;
    }

    // Extract service ID from the value (format: "id|name plan")
    const serviceId = selectedService.split("|")[0];

    try {
      setSimulating(true);
      setOutput(""); // Clear previous output
      const response = await fetch("/api/simulation/cmd", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          service_id: parseInt(serviceId, 10),
          name: selectedCommandGroup,
          command: selectedCommand,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to execute simulation command");
      }

      const result = await response.json();
      console.log("Simulation result:", result);
      
      // Set the output from the response
      if (typeof result === 'string') {
        setOutput(result);
      } else if (result.output) {
        setOutput(result.output);
      } else {
        setOutput(JSON.stringify(result, null, 2));
      }
      // You can add a toast notification here for success
    } catch (error) {
      console.error("Error executing simulation:", error);
      setOutput(`Error: ${error instanceof Error ? error.message : 'Failed to execute command'}`);
      // You can add a toast notification here for error
    } finally {
      setSimulating(false);
    }
  };

  return (
    <div className="rounded-lg border bg-card text-card-foreground shadow-sm overflow-hidden">
      {/* Header with Illustration */}
      <div className="relative h-64 w-full bg-linear-to-t from-primary/5 to-emerald-500/10">
        <div className="absolute top-0 left-0 right-0 flex items-center justify-between p-6 z-10">
          <h3 className="text-lg font-semibold">Simulate Lab Environment</h3>
          <Button variant="ghost" size="icon" className="size-6">
            <Info className="size-4 text-muted-foreground" />
          </Button>
        </div>
        <Image
          src={simulateEnvIll}
          alt="Simulate environment illustration"
          className="object-contain object-center p-4 pt-16"
          fill
          priority
        />
      </div>

      {/* Content */}
      <div className="p-6 space-y-4">
        {/* Service Selection */}
        <div className="space-y-2">
          <label className="text-xs text-muted-foreground font-medium">Customer Service</label>
          <div className="flex items-end gap-2">
            <Home className="size-6 text-muted-foreground" />
            <Combobox
              options={serviceOptions}
              value={selectedService}
              onValueChange={setSelectedService}
              placeholder={loading ? "Loading services..." : "Select a service..."}
              searchPlaceholder="Search services..."
              emptyText="No active services found."
              disabled={loading}
              className="flex-1"
            />
          </div>
        </div>

        {/* Command Group Selection - Only show when service is selected */}
        {selectedService && (
          <div className="space-y-2">
            <label className="text-xs text-muted-foreground font-medium">Command Group</label>
            <div className="flex items-end gap-2">
              <Network className="size-6 text-muted-foreground" />
              <Combobox
                options={commandGroupOptions}
                value={selectedCommandGroup}
                onValueChange={(value) => {
                  setSelectedCommandGroup(value);
                  setSelectedCommand(""); // Reset command when group changes
                }}
                placeholder="Select command group..."
                searchPlaceholder="Search command groups..."
                emptyText="No command groups available."
                className="flex-1"
              />
            </div>
          </div>
        )}

        {/* Command Selection - Only show when command group is selected */}
        {selectedService && selectedCommandGroup && (
          <div className="space-y-2">
            <label className="text-xs text-muted-foreground font-medium">Command</label>
            <div className="flex items-end gap-2">
              <Bug className="size-6 text-muted-foreground" />
              <Combobox
                options={commandOptions}
                value={selectedCommand}
                onValueChange={setSelectedCommand}
                placeholder="Select command..."
                searchPlaceholder="Search commands..."
                emptyText="No commands available."
                className="flex-1"
              />
            </div>
          </div>
        )}

        {/* Note Display - Show when command group is selected and has a note */}
        {selectedCommandGroup && (() => {
          const selectedGroupData = simulateOptions.find((opt) => opt.name === selectedCommandGroup);
          if (!selectedGroupData?.note) return null;
          
          const isWarning = selectedGroupData.note.type === "warning";
          
          return (
            <div className={`rounded-lg border p-3 flex items-start gap-3 ${
              isWarning 
                ? "bg-amber-50 border-amber-200 text-amber-900" 
                : "bg-blue-50 border-blue-200 text-blue-900"
            }`}>
              {isWarning ? (
                <AlertTriangle className="size-5 text-amber-600 shrink-0 mt-0.5" />
              ) : (
                <Info className="size-5 text-blue-600 shrink-0 mt-0.5" />
              )}
              <p className="text-xs italic">{selectedGroupData.note.text}</p>
            </div>
          );
        })()}

        {/* Simulate Button */}
        <Button 
          onClick={handleSimulate} 
          className="w-full" 
          size="lg"
          disabled={!selectedService || !selectedCommandGroup || !selectedCommand || loading || simulating}
        >
          {simulating ? "Simulating..." : "Simulate Subscriber"}
        </Button>

        {/* Elapsed Time Spinner - Show while simulating */}
        {simulating && (
          <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
            <Spinner className="size-4" />
            <span className="font-mono">{elapsedTime.toFixed(2)}s</span>
          </div>
        )}

        {/* Output Display - Show when output exists */}
        {output && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-medium">Output</h4>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setOutputDialogOpen(true)}
                  className="h-7 text-xs"
                >
                  <Maximize2 className="size-3 mr-1" />
                  Expand
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setOutput("")}
                  className="h-7 text-xs"
                >
                  Clear
                </Button>
              </div>
            </div>
            <div className="rounded-md bg-muted p-4 font-mono text-xs overflow-x-auto max-h-40 overflow-y-auto">
              <pre className="whitespace-pre-wrap wrap-break-word">{output}</pre>
            </div>
          </div>
        )}

        {/* Description */}
        <p className="text-xs text-muted-foreground">
          Simulate lab subscribers connecting via DHCPv4 and generate traffic directly from
          the dashboard without requiring SSH or manual CLI commands.
        </p>
      </div>

      {/* Output Dialog */}
      <Dialog open={outputDialogOpen} onOpenChange={setOutputDialogOpen}>
        <DialogContent className="max-w-6xl lg:min-w-3xl max-h-[80vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>Command Output</DialogTitle>
            <DialogDescription>
              Full output from the simulation command
            </DialogDescription>
          </DialogHeader>
          <div className="flex-1 overflow-auto rounded-md bg-muted p-4 font-mono text-sm">
            <pre className="whitespace-pre-wrap wrap-break-word">{output}</pre>
          </div>
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                navigator.clipboard.writeText(output);
              }}
            >
              Copy to Clipboard
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setOutputDialogOpen(false)}
            >
              Close
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
