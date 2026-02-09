"use client";

import { ArrowDown, ArrowUp, Activity, History, Calendar } from "lucide-react";
import { useEffect, useState } from "react";

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

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

export function SectionCards() {
  const [stats, setStats] = useState<StatsData | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await fetch('/api/stats');
        if (response.ok) {
          const data = await response.json();
          setStats(data);
        }
      } catch (error) {
        console.error('Failed to fetch stats:', error);
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 2000); // Poll every 2 seconds

    return () => clearInterval(interval);
  }, []);

  if (!stats) {
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
          <CardDescription>Session History</CardDescription>
          <CardTitle className="font-semibold @[250px]/card:text-3xl text-2xl tabular-nums">
            {stats.history_sessions}
          </CardTitle>
          <CardAction>
            <Badge variant="outline">
              <History className="size-3" />
              Total
            </Badge>
          </CardAction>
        </CardHeader>
        <CardFooter className="flex-col items-start gap-1.5 text-sm">
          <div className="line-clamp-1 flex gap-2 font-medium">
            Historical sessions <History className="size-4" />
          </div>
          <div className="text-muted-foreground">Completed session records</div>
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
      
      <Card className="@container/card">
        <CardHeader>
          <CardDescription>Active Traffic</CardDescription>
          <CardTitle className="font-semibold @[250px]/card:text-xl text-lg tabular-nums flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <ArrowDown className="size-4 text-blue-500" />
              <span>{formatBytes(stats.active_traffic.input_octets)}</span>
              <span className="text-sm text-muted-foreground">({stats.active_traffic.input_packets} pkts)</span>
            </div>
            <div className="flex items-center gap-2">
              <ArrowUp className="size-4 text-green-500" />
              <span>{formatBytes(stats.active_traffic.output_octets)}</span>
              <span className="text-sm text-muted-foreground">({stats.active_traffic.output_packets} pkts)</span>
            </div>
          </CardTitle>
        </CardHeader>
        <CardFooter className="flex-col items-start gap-1.5 text-sm">
          <div className="line-clamp-1 flex gap-2 font-medium">
            Network traffic volume
          </div>
          <div className="text-muted-foreground">Download / Upload (octets & packets)</div>
        </CardFooter>
      </Card>
    </div>
  );
}
