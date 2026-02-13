"use client";

import { useEffect, useState } from "react";
import { Activity, CircleIcon, CircleSmallIcon, Server } from "lucide-react";
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

  useEffect(() => {
    const fetchBngs = async () => {
      try {
        console.log("Fetching BNGs...");
        const response = await fetch('/api/bngs');
        if (response.ok) {
          const result = await response.json();
          console.log("BNGs data:", result);
          setBngs(result.data);

          // Fetch health data for each BNG
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
        
        console.log(`Health data for ${bng.bng_id}:`, health);
        
        // Prepare chart data (reverse to show oldest to newest)
        const chartData = [...health].reverse().map((h) => ({
          time: formatTimestamp(h.ts),
          cpu: parseFloat(h.cpu_usage),
          memory: ((parseFloat(h.mem_usage) / parseFloat(h.mem_max)) * 100),
        }));

        console.log(`Chart data for ${bng.bng_id}:`, chartData);

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

        return (
          <Card key={bng.bng_id} className="overflow-hidden p-0 pt-6">
            <CardHeader>
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <CardTitle className="flex items-center gap-2">
                    <Server className="h-5 w-5" />
                    <div className="flex flex-col gap-1">
                        {bng.bng_id}
                        <span className="font-mono text-[10px] truncate font-light text-gray-500">
                            {bng.bng_instance_id}
                        </span>
                    </div>
                  </CardTitle>
                </div>
                <Badge 
                  variant={isAlive ? "default" : "secondary"}
                  className={isAlive ? "bg-green-500/10 text-green-700 dark:text-green-400 border-green-500/20" : ""}
                >
                  {isAlive ? <Activity className="mr-1 h-3 w-3" /> : null}
                  {isAlive ? "Online" : "Offline"}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4 pb-0">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                    <div className="flex gap-1 items-baseline">
                        <p className="text-muted-foreground">CPU Usage</p>
                        <CircleIcon className="h-2 w-2" fill="#8884d8"/>
                    </div>
                  <p className="font-semibold text-lg tabular-nums">{cpuUsage}%</p>
                  {/* A small badge like circle */}
                </div>
                <div>
                    <div className="flex gap-1 items-baseline">
                        <p className="text-muted-foreground">Memory</p>
                        <CircleIcon className="h-2 w-2" fill="#82ca9d"/>
                    </div>
                  <p className="font-semibold text-lg tabular-nums">{memPercent}%</p>
                  <p className="text-muted-foreground text-xs">
                    {formatMemory(memUsage)} / {formatMemory(memMax)}
                  </p>
                </div>
              </div>
            </CardContent>
            
            <CardContent className="flex-1 p-0">
              {chartData.length > 0 ? (
                <ChartContainer className="h-32 w-full" config={chartConfig}>
                    <AreaChart
                      data={chartData}
                      margin={{
                        left: 0,
                        right: 0,
                        top: 5,
                        bottom: 0,
                      }}
                    >
                      <XAxis 
                        dataKey="time" 
                        tickLine={false} 
                        tickMargin={10} 
                        axisLine={false} 
                        hide 
                      />
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
                        fill="#8884d8"
                        fillOpacity={0.2}
                        stroke="#8884d8"
                        strokeWidth={2}
                        type="monotone"
                      />
                      <Area
                        
                        dataKey="memory"
                        fill="#82ca9d"
                        fillOpacity={0.2}
                        stroke="#82ca9d"
                        strokeWidth={2}
                        type="monotone"
                      />
                    </AreaChart>
                    
                  </ChartContainer>
                ) : (
                  <div className="h-32 flex items-center justify-center text-muted-foreground text-sm">
                    Loading chart data...
                  </div>
                )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
