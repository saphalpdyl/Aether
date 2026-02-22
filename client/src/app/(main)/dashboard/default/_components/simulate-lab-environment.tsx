"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import { ChevronDown, Home, Network, Bug, Info } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
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

interface SimulateOption {
  name: string;
  commands: string[];
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
  const commandGroupOptions: ComboboxOption[] = simulateOptions.map((option) => {
    // Format label: capitalize first letter and replace underscores with spaces
    const formattedLabel = option.name
      .replace(/_/g, ' ').toUpperCase();    
    return {
      value: option.name,
      label: formattedLabel,
    };
  });

  // Get commands for selected group
  const selectedGroup = simulateOptions.find((opt) => opt.name === selectedCommandGroup);
  const commandOptions: ComboboxOption[] = selectedGroup
    ? selectedGroup.commands.map((cmd) => ({
        value: cmd,
        label: cmd,
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
      // You can add a toast notification here for success
    } catch (error) {
      console.error("Error executing simulation:", error);
      // You can add a toast notification here for error
    } finally {
      setSimulating(false);
    }
  };

  return (
    <div className="rounded-lg border bg-card text-card-foreground shadow-sm overflow-hidden">
      {/* Header with Illustration */}

      {/* Content */}
      <div className="p-6 pt-0 space-y-4">
        <div className="relative h-64 w-full">
            <div className="flex items-center justify-between pt-3">
            <h3 className="text-lg font-semibold">Simulate Lab Environment</h3>
            <Button variant="ghost" size="icon" className="size-6">
                <Info className="size-4 text-muted-foreground" />
            </Button>
            </div>

            <Image
            src={simulateEnvIll}
            alt="Simulate environment illustration"
            className="object-contain object-center p-4"
            priority
            />
        </div>

        {/* Service Selection */}
        <div className="space-y-2 flex items-end gap-2">
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

        {/* Command Group Selection - Only show when service is selected */}
        {selectedService && (
          <div className="space-y-2 flex items-end gap-2">
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
        )}

        {/* Command Selection - Only show when command group is selected */}
        {selectedService && selectedCommandGroup && (
          <div className="space-y-2 flex items-end gap-2">
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
        )}

        {/* Simulate Button */}
        <Button 
          onClick={handleSimulate} 
          className="w-full" 
          size="lg"
          disabled={!selectedService || !selectedCommandGroup || !selectedCommand || loading || simulating}
        >
          {simulating ? "Simulating..." : "Simulate Subscriber"}
        </Button>

        {/* Description */}
        <p className="text-xs text-muted-foreground">
          Simulate lab subscribers connecting via DHCP / DHCPv6 and generate traffic directly from
          the dashboard without requiring SSH or manual CLI commands.
        </p>
      </div>
    </div>
  );
}
