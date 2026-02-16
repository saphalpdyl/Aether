"use client";

import { useState } from "react";
import Image from "next/image";
import { ChevronDown, Home, Network, Bug, Info } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import simulateEnvIll from "@/assets/illustrations/simulate_env_ill.png";

export function SimulateLabEnvironment() {
  const [selectedRouter, setSelectedRouter] = useState("r01");
  const [dhcpEnabled, setDhcpEnabled] = useState(true);
  const [trafficEnabled, setTrafficEnabled] = useState(true);
  const [debuggingEnabled, setDebuggingEnabled] = useState(false);

  const routers = [
    { id: "r01", name: "R01 - WDSL 40 Mbps" },
    { id: "r02", name: "R02 - Fiber 100 Mbps" },
    { id: "r03", name: "R03 - Cable 50 Mbps" },
  ];

  const handleSimulate = () => {
    console.log("Simulating with:", {
      router: selectedRouter,
      dhcp: dhcpEnabled,
      traffic: trafficEnabled,
      debugging: debuggingEnabled,
    });
    // Add simulation logic here
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

        {/* Router Selection */}
        <div className="space-y-2 flex items-end gap-2">
            <Home className="size-6 text-muted-foreground" />
          <Select value={selectedRouter} onValueChange={setSelectedRouter}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {routers.map((router) => (
                <SelectItem key={router.id} value={router.id}>
                  {router.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Options */}
        <div className="flex items-center gap-3 flex-wrap">
          <button
            onClick={() => setDhcpEnabled(!dhcpEnabled)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm transition-colors ${
              dhcpEnabled
                ? "bg-muted text-foreground"
                : "bg-transparent text-muted-foreground hover:bg-muted/50"
            }`}
          >
            <Network className="size-4" />
            DHCP
            {dhcpEnabled && (
              <div className="size-2 rounded-full bg-green-500" />
            )}
          </button>

          <button
            onClick={() => setTrafficEnabled(!trafficEnabled)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm transition-colors ${
              trafficEnabled
                ? "bg-green-500/10 text-green-700 dark:text-green-400 border border-green-500/20"
                : "bg-transparent text-muted-foreground hover:bg-muted/50"
            }`}
          >
            <div className="size-2 rounded-full bg-green-500" />
            Traffic
          </button>

          <button
            onClick={() => setDebuggingEnabled(!debuggingEnabled)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm transition-colors ${
              debuggingEnabled
                ? "bg-blue-500/10 text-blue-700 dark:text-blue-400 border border-blue-500/20"
                : "bg-transparent text-muted-foreground hover:bg-muted/50"
            }`}
          >
            <div className="size-2 rounded-full bg-blue-500" />
            Debugging
          </button>
        </div>

        {/* Simulate Button */}
        <Button onClick={handleSimulate} className="w-full" size="lg">
          Simulate Subscriber
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
