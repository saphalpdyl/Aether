"use client";

import { useEffect, useRef, useState } from "react";

import Image from "next/image";
import { useTheme } from "next-themes";

import { Activity, ArrowDown, ArrowUp, Calendar, Server } from "lucide-react";
import { Area, AreaChart, ResponsiveContainer } from "recharts";

import activeTrafficIll from "@/assets/illustrations/active_traffic_ill.png";
import { Badge } from "@/components/ui/badge";
import { Card, CardAction, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { AnimatedCounter } from "@/components/ui/animated-counter";

interface StatsData {
  active_sessions: number;
  history_sessions: number;
  total_events: number;
  active_traffic: {
    input_octets: number;
    output_octets: number;
    input_packets: number;
    output_packets: number;
  };
}

interface RoutersData {
  data: Array<{
    is_alive: string;
  }>;
  count: number;
}

interface TrafficHistoryPoint {
  ts: string;
  in_bps: number;
  out_bps: number;
  total_bps: number;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / k ** i).toFixed(2))} ${sizes[i]}`;
}

function formatRate(bps: number): { value: string; unit: string } {
  if (bps >= 1_000_000_000) {
    return { value: (bps / 1_000_000_000).toFixed(1), unit: "Gbps" };
  }
  if (bps >= 1_000_000) {
    return { value: (bps / 1_000_000).toFixed(0), unit: "Mbps" };
  }
  if (bps >= 1_000) {
    return { value: (bps / 1_000).toFixed(0), unit: "Kbps" };
  }
  return { value: bps.toFixed(0), unit: "bps" };
}

export function SectionCards() {
  const { resolvedTheme } = useTheme();
  const [stats, setStats] = useState<StatsData | null>(null);
  const [routers, setRouters] = useState<RoutersData | null>(null);
  const [trafficHistory, setTrafficHistory] = useState<TrafficHistoryPoint[]>([]);
  const baselineTrafficRef = useRef<{
    tsMs: number;
    inputOctets: number;
    outputOctets: number;
  } | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await fetch("/api/stats");
        if (response.ok) {
          const data = await response.json();
          setStats(data);

          const nowMs = Date.now();
          const inputOctets = Number(data.active_traffic?.input_octets || 0);
          const outputOctets = Number(data.active_traffic?.output_octets || 0);

          // Initialize baseline if not set
          if (!baselineTrafficRef.current) {
            baselineTrafficRef.current = {
              tsMs: nowMs,
              inputOctets,
              outputOctets,
            };
          }

          // Calculate bps over 5-minute window
          const fiveMinutesMs = 5 * 60 * 1000;
          const baselineTraffic = baselineTrafficRef.current;
          const elapsedSeconds = Math.max((nowMs - baselineTraffic.tsMs) / 1000, 0.001);
          const inDelta = Math.max(inputOctets - baselineTraffic.inputOctets, 0);
          const outDelta = Math.max(outputOctets - baselineTraffic.outputOctets, 0);
          const inBps = (inDelta * 8) / elapsedSeconds;
          const outBps = (outDelta * 8) / elapsedSeconds;

          // Reset baseline every 5 minutes
          if (nowMs - baselineTraffic.tsMs >= fiveMinutesMs) {
            baselineTrafficRef.current = {
              tsMs: nowMs,
              inputOctets,
              outputOctets,
            };
          }

          setTrafficHistory((prev) => {
            const next = [
              ...prev,
              {
                ts: new Date(nowMs).toISOString(),
                in_bps: inBps,
                out_bps: outBps,
                total_bps: inBps + outBps,
              },
            ];
            return next.slice(-40);
          });
        }
      } catch (error) {
        console.error("Failed to fetch stats:", error);
      }
    };

    const fetchRouters = async () => {
      try {
        const response = await fetch("/api/routers");
        if (response.ok) {
          const data = await response.json();
          setRouters(data);
        }
      } catch (error) {
        console.error("Failed to fetch routers:", error);
      }
    };

    fetchStats();
    fetchRouters();
    const interval = setInterval(() => {
      fetchStats();
      fetchRouters();
    }, 2000); // Poll every 2 seconds

    return () => clearInterval(interval);
  }, []);

  if (!stats || !routers) {
    return (
      <div className="grid @5xl/main:grid-cols-4 @xl/main:grid-cols-2 grid-cols-1 gap-4">
        <Card className="@container/card animate-pulse">
          <CardHeader>
            <CardDescription>Loading...</CardDescription>
            <CardTitle className="font-semibold @[250px]/card:text-3xl text-2xl tabular-nums">-</CardTitle>
          </CardHeader>
        </Card>
      </div>
    );
  }

  const onlineRouters = routers.data.filter((r) => r.is_alive.toLowerCase() === "true").length;

  const hasTrafficHistory = trafficHistory.some((point) => point.total_bps > 0);
  const latestTraffic = trafficHistory[trafficHistory.length - 1] ?? { in_bps: 0, out_bps: 0, total_bps: 0 };
  const inRate = formatRate(latestTraffic.in_bps);
  const outRate = formatRate(latestTraffic.out_bps);

  const isDark = resolvedTheme === "dark";
  const gradientColor = isDark ? "hsl(var(--chart-1))" : "hsl(var(--primary))";
  const gradientOpacity = isDark ? 0.4 : 0.3;

  return (
    <div className="grid @5xl/main:grid-cols-[1fr_1fr_1fr_1.7fr] @xl/main:grid-cols-2 grid-cols-1 gap-4">
      <Card className="@container/card">
        <CardHeader>
          <CardDescription>Active Sessions</CardDescription>
          <CardTitle className="font-semibold @[250px]/card:text-3xl text-2xl tabular-nums">
            <AnimatedCounter value={stats.active_sessions} />
          </CardTitle>
          <CardAction>
            <Badge variant="outline" className="bg-green-500/10 text-green-700 dark:text-green-400 border-green-500/20">
              <Activity className="size-3" />
              Live
            </Badge>
          </CardAction>
        </CardHeader>
        <CardFooter className="flex-col items-start gap-1.5 text-sm">
          <div className="line-clamp-1 flex gap-2 font-medium">
            Currently active users <Activity className="size-4" />
          </div>
          <div className="text-muted-foreground">Real-time session count</div>
        </CardFooter>
      </Card>

      <Card className="@container/card">
        <CardHeader>
          <CardDescription>Access nodes online</CardDescription>
          <CardTitle className="font-semibold @[250px]/card:text-3xl text-2xl tabular-nums">
            <AnimatedCounter value={onlineRouters} /> / <AnimatedCounter value={routers.count} />
          </CardTitle>
          <CardAction>
            <Badge variant="outline" className="bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/20">
              <Server className="size-3" />
              Active
            </Badge>
          </CardAction>
        </CardHeader>
        <CardFooter className="flex-col items-start gap-1.5 text-sm">
          <div className="line-clamp-1 flex gap-2 font-medium">
            Access nodes status <Server className="size-4" />
          </div>
          <div className="text-muted-foreground">Online nodes / Total nodes</div>
        </CardFooter>
      </Card>

      <Card className="@container/card">
        <CardHeader>
          <CardDescription>Total Events</CardDescription>
          <CardTitle className="font-semibold @[250px]/card:text-3xl text-2xl tabular-nums">
            <AnimatedCounter value={stats.total_events} />
          </CardTitle>
          <CardAction>
            <Badge variant="outline">
              <Calendar className="size-3" />
              Events
            </Badge>
          </CardAction>
        </CardHeader>
        <CardFooter className="flex-col items-start gap-1.5 text-sm">
          <div className="line-clamp-1 flex gap-2 font-medium">
            System events logged <Calendar className="size-4" />
          </div>
          <div className="text-muted-foreground">All session lifecycle events</div>
        </CardFooter>
      </Card>

      <Card className="@container/card flex flex-col p-0 overflow-hidden relative w-full">
        <div className="flex flex-row justify-between w-full">
          <CardHeader className="p-8 w-2/3 z-10">
            <CardDescription>Active Traffic</CardDescription>
            <CardTitle className="space-y-2">
              <div className="flex gap-1.5 divide-x-2 space-x-4 w-full">
                <div className="flex flex-col items-baseline gap-1.5 pr-8">
                  <div className="space-x-1">
                    <div className="font-semibold @[250px]/card:text-3xl text-2xl tabular-nums inline">
                      <AnimatedCounter value={parseFloat(inRate.value)} decimals={1} />
                    </div>
                    <span className="text-lg font-semibold text-cyan-500">{inRate.unit}</span>
                  </div>
                  <span className="ml-2 text-xs text-muted-foreground flex items-center gap-1">
                    <ArrowDown className="size-3 text-cyan-500" />
                    {formatBytes(stats.active_traffic.input_octets)} down
                  </span>
                </div>
                <div className="flex items-baseline gap-1.5 flex-col">
                  <div className="space-x-1">
                    <div className="font-semibold @[250px]/card:text-3xl text-2xl tabular-nums inline">
                      <AnimatedCounter value={parseFloat(outRate.value)} decimals={1} />
                    </div>
                    <span className="text-lg font-semibold text-green-500">{outRate.unit}</span>
                  </div>
                  <span className="ml-2 text-xs text-muted-foreground flex items-center gap-1">
                    <ArrowUp className="size-3 text-green-500" />
                    {formatBytes(stats.active_traffic.output_octets)} up
                  </span>
                </div>
              </div>
            </CardTitle>
          </CardHeader>
          <div className="absolute h-full w-96 mr-6 -right-28 z-8">
            <div className="absolute inset-0 bg-linear-to-r from-card via-card/50 to-transparent z-10 pointer-events-none" />
            <Image
              src={activeTrafficIll}
              alt="Active traffic illustration"
              height={500}
              width={300}
              className="object-contain object-center z-8"
              priority
            />
          </div>
        </div>
        <div className="h-16 w-full absolute z-12 bottom-0">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={trafficHistory}>
              <defs>
                <linearGradient id="trafficGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={gradientColor} stopOpacity={gradientOpacity} />
                  <stop offset="100%" stopColor={gradientColor} stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area
                type="monotone"
                dataKey="total_bps"
                stroke={gradientColor}
                fill="url(#trafficGradient)"
                strokeWidth={2}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Card>
    </div>
  );
}
