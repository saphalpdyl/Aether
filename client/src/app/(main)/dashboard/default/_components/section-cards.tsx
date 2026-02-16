"use client";

import { useEffect, useRef, useState } from "react";

import { Activity, ArrowDown, ArrowUp, Calendar, Server } from "lucide-react";
import { Area, AreaChart, ResponsiveContainer } from "recharts";

import { Badge } from "@/components/ui/badge";
import { Card, CardAction, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";

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

export function SectionCards() {
  const [stats, setStats] = useState<StatsData | null>(null);
  const [routers, setRouters] = useState<RoutersData | null>(null);
  const [trafficHistory, setTrafficHistory] = useState<TrafficHistoryPoint[]>([]);
  const lastTrafficSampleRef = useRef<{
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

          const lastTrafficSample = lastTrafficSampleRef.current;
          if (lastTrafficSample) {
            const elapsedSeconds = Math.max((nowMs - lastTrafficSample.tsMs) / 1000, 0.001);
            const inDelta = Math.max(inputOctets - lastTrafficSample.inputOctets, 0);
            const outDelta = Math.max(outputOctets - lastTrafficSample.outputOctets, 0);
            const inBps = (inDelta * 8) / elapsedSeconds;
            const outBps = (outDelta * 8) / elapsedSeconds;

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
          } else {
            setTrafficHistory((prev) => {
              const next = [
                ...prev,
                {
                  ts: new Date(nowMs).toISOString(),
                  in_bps: 0,
                  out_bps: 0,
                  total_bps: 0,
                },
              ];
              return next.slice(-40);
            });
          }

          lastTrafficSampleRef.current = {
            tsMs: nowMs,
            inputOctets,
            outputOctets,
          };
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

  return (
    <div className="grid @5xl/main:grid-cols-4 @xl/main:grid-cols-2 grid-cols-1 gap-4 *:data-[slot=card]:bg-linear-to-t *:data-[slot=card]:from-primary/5 *:data-[slot=card]:to-card *:data-[slot=card]:shadow-xs dark:*:data-[slot=card]:bg-card">
      <Card className="@container/card">
        <CardHeader>
          <CardDescription>Active Sessions</CardDescription>
          <CardTitle className="font-semibold @[250px]/card:text-3xl text-2xl tabular-nums">
            {stats.active_sessions}
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
            {onlineRouters} / {routers.count}
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
            {stats.total_events}
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
      
      <Card className="@container/card relative overflow-hidden">
        <div className="absolute inset-0 pointer-events-none opacity-70">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={trafficHistory}>
              <defs>
                <linearGradient id="trafficIn" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.45} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="trafficOut" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22c55e" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#22c55e" stopOpacity={0.01} />
                </linearGradient>
              </defs>
              <Area type="monotone" dataKey="out_bps" stroke="#22c55e" strokeWidth={1.5} fill="url(#trafficOut)" />
              <Area type="monotone" dataKey="in_bps" stroke="#3b82f6" strokeWidth={1.5} fill="url(#trafficIn)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <CardHeader className="relative z-10">
          <CardDescription>Active Traffic</CardDescription>
          <CardTitle className="font-semibold @[250px]/card:text-xl text-lg tabular-nums flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <ArrowDown className="size-4 text-blue-500" />
              <span className="text-sm">{formatBytes(stats.active_traffic.input_octets)}</span>
              <span className="text-sm text-muted-foreground">({stats.active_traffic.input_packets} pkts)</span>
            </div>
            <div className="flex items-center gap-2">
              <ArrowUp className="size-4 text-green-500" />
              <span className="text-sm">{formatBytes(stats.active_traffic.output_octets)}</span>
              <span className="text-sm text-muted-foreground">({stats.active_traffic.output_packets} pkts)</span>
            </div>
          </CardTitle>
        </CardHeader>
        <CardFooter className="relative z-10 flex-col items-start gap-1.5 text-sm">
          <div className="line-clamp-1 flex gap-2 font-medium">
            Network traffic volume {hasTrafficHistory ? null : "(waiting for samples)"}
          </div>
          <div className="text-muted-foreground">Download / Upload (octets & packets)</div>
        </CardFooter>
      </Card>
    </div>
  );
}
