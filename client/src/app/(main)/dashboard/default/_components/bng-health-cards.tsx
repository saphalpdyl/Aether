"use client";

import { useEffect, useState } from "react";
import { Area, AreaChart, XAxis } from "recharts";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";

interface BngData {
  bng_id: string;
  bng_instance_id: string;
  first_seen: string;
  last_seen: string;
  is_alive: string;
  cpu_usage: string;
  mem_usage: string;
  mem_max: string;
}

interface HealthData {
  bng_id: string;
  bng_instance_id: string;
  ts: string;
  cpu_usage: string;
  mem_usage: string;
  mem_max: string;
}

interface RouterData {
  router_name: string;
  giaddr: string;
  bng_id: string;
  is_alive: boolean;
  active_subscribers: number;
}

function formatMemory(mb: number): string {
  if (mb >= 1024) {
    return `${(mb / 1024).toFixed(2)} GB`;
  }
  return `${mb.toFixed(2)} MB`;
}

function formatTimestamp(ts: string): string {
  const date = new Date(ts);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function BngHealthCards() {
  const [bngs, setBngs] = useState<BngData[]>([]);
  const [healthData, setHealthData] = useState<Map<string, HealthData[]>>(new Map());
  const [routerData, setRouterData] = useState<Map<string, RouterData[]>>(new Map());

  useEffect(() => {
    const fetchBngs = async () => {
      try {
        console.log("Fetching BNGs...");
        const response = await fetch('/api/bngs');
        if (response.ok) {
          const result = await response.json();
          console.log("BNGs data:", result);
          setBngs(result.data);

          // Fetch health data and routers for each BNG
          for (const bng of result.data) {
            try {
              console.log(`Fetching health for ${bng.bng_id}/${bng.bng_instance_id}`);
              const healthResponse = await fetch(
                `/api/bngs/${bng.bng_id}/health/${bng.bng_instance_id}`
              );
              if (healthResponse.ok) {
                const healthResult = await healthResponse.json();
                console.log(`Health data for ${bng.bng_id}:`, healthResult);
                setHealthData(prev => {
                  const newMap = new Map(prev);
                  newMap.set(bng.bng_id, healthResult.data);
                  return newMap;
                });
              } else {
                console.error(`Failed to fetch health for ${bng.bng_id}, status:`, healthResponse.status);
              }
            } catch (error) {
              console.error(`Failed to fetch health for ${bng.bng_id}:`, error);
            }

            // Fetch routers for this BNG
            try {
              const routersResponse = await fetch(`/api/routers?bng_id=${bng.bng_id}`);
              if (routersResponse.ok) {
                const routersResult = await routersResponse.json();
                setRouterData(prev => {
                  const newMap = new Map(prev);
                  newMap.set(bng.bng_id, routersResult.data);
                  return newMap;
                });
              }
            } catch (error) {
              console.error(`Failed to fetch routers for ${bng.bng_id}:`, error);
            }
          }
        }
      } catch (error) {
        console.error('Failed to fetch BNGs:', error);
      }
    };

    fetchBngs();
    const interval = setInterval(fetchBngs, 5000); // Poll every 5 seconds

    return () => clearInterval(interval);
  }, []);

  if (bngs.length === 0) {
    return (
      <div className="grid grid-cols-1 gap-4">
        <Card className="animate-pulse">
          <CardHeader>
            <CardDescription>Loading BNG Health...</CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {bngs.map((bng) => {
        const isAlive = bng.is_alive.toLowerCase() === 'true';
        const cpuUsage = parseFloat(bng.cpu_usage);
        const memUsage = parseFloat(bng.mem_usage);
        const memMax = parseFloat(bng.mem_max);
        const memPercent = ((memUsage / memMax) * 100).toFixed(1);
        
        const health = healthData.get(bng.bng_id) || [];
        const routers = routerData.get(bng.bng_id) || [];
        
        // Prepare chart data (reverse to show oldest to newest)
        const chartData = [...health].reverse().map((h) => ({
          time: formatTimestamp(h.ts),
          cpu: parseFloat(h.cpu_usage),
          memory: ((parseFloat(h.mem_usage) / parseFloat(h.mem_max)) * 100),
        }));

        const chartConfig = {
          cpu: {
            label: "CPU Usage",
            color: "hsl(var(--chart-1))",
          },
          memory: {
            label: "Memory Usage",
            color: "hsl(var(--chart-2))",
          },
        };

        // Calculate total subscribers and interfaces
        const totalSubscribers = routers.reduce((sum, r) => sum + (r.active_subscribers || 0), 0);
        const routerCount = routers.length;

        return (
          <Card key={bng.bng_id} className="overflow-hidden">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  BNG Overview
                </CardTitle>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-base font-semibold">{bng.bng_id}</span>
                </div>
                <Badge 
                  variant="outline"
                  className={isAlive ? "bg-green-50 text-green-700 border-green-200" : "bg-gray-50 text-gray-700 border-gray-200"}
                >
                  {isAlive ? "Online" : "Offline"}
                </Badge>
              </div>
            </CardHeader>
            
            <CardContent className="space-y-3 pb-3">
              {/* CPU and Memory Usage */}
              <div className="grid grid-cols-2 gap-4 divide-x">
                <div>
                  <div className="flex items-baseline gap-1">
                    <p className="text-xs text-muted-foreground">CPU Usage</p>
                    <div className="w-2 h-2 rounded-full bg-blue-500" />
                  </div>
                  <p className="text-2xl font-bold tabular-nums mt-1">{cpuUsage.toFixed(1)}%</p>
                  <p className="text-xs text-muted-foreground">3d Avg</p>
                </div>
                <div className="pl-4">
                  <div className="flex items-baseline gap-1">
                    <p className="text-xs text-muted-foreground">Memory</p>
                    <div className="w-2 h-2 rounded-full bg-green-500" />
                  </div>
                  <p className="text-2xl font-bold tabular-nums mt-1">{memPercent}%</p>
                  <p className="text-xs text-muted-foreground">
                    {formatMemory(memUsage)} / {formatMemory(memMax)}
                  </p>
                </div>
              </div>

              {/* Chart */}
              {chartData.length > 0 && (
                <div className="h-24 -mx-2">
                  <ChartContainer className="h-full w-full" config={chartConfig}>
                    <AreaChart
                      data={chartData}
                      margin={{ left: 0, right: 0, top: 5, bottom: 0 }}
                    >
                      <XAxis dataKey="time" hide />
                      <ChartTooltip
                        content={
                          <ChartTooltipContent 
                            labelFormatter={(label) => `Time: ${label}`}
                            formatter={(value, name) => [
                              `${Number(value).toFixed(1)}%`,
                              name === 'cpu' ? 'CPU' : 'Memory'
                            ]}
                          />
                        }
                      />
                      <Area
                        dataKey="cpu"
                        fill="#3b82f6"
                        fillOpacity={0.2}
                        stroke="#3b82f6"
                        strokeWidth={2}
                        type="monotone"
                      />
                      <Area
                        dataKey="memory"
                        fill="#10b981"
                        fillOpacity={0.2}
                        stroke="#10b981"
                        strokeWidth={2}
                        type="monotone"
                      />
                    </AreaChart>
                  </ChartContainer>
                </div>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
