"use client";

import * as React from "react";

import { Area, AreaChart, CartesianGrid, XAxis } from "recharts";

import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { type ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useIsMobile } from "@/hooks/use-mobile";

type RangeKey = "15m" | "1h" | "6h" | "24h";

type TrafficPoint = {
  ts: string;
  bps_in: number;
  bps_out: number;
  bps_total: number;
};

const chartConfig = {
  bps_in: {
    label: "Ingress",
    color: "var(--chart-1)",
  },
  bps_out: {
    label: "Egress",
    color: "var(--chart-2)",
  },
  bps_total: {
    label: "Total",
    color: "var(--chart-3)",
  },
} satisfies ChartConfig;

function formatRate(bps: number): string {
  if (bps >= 1_000_000_000) {
    return `${(bps / 1_000_000_000).toFixed(2)} Gbps`;
  }
  if (bps >= 1_000_000) {
    return `${(bps / 1_000_000).toFixed(2)} Mbps`;
  }
  if (bps >= 1_000) {
    return `${(bps / 1_000).toFixed(2)} Kbps`;
  }
  return `${bps.toFixed(0)} bps`;
}

function bucketSecondsForRange(range: RangeKey): number {
  switch (range) {
    case "15m":
      return 5;
    case "1h":
      return 10;
    case "6h":
      return 30;
    case "24h":
      return 60;
    default:
      return 10;
  }
}

export function ChartAreaInteractive() {
  const isMobile = useIsMobile();
  const [timeRange, setTimeRange] = React.useState<RangeKey>("1h");
  const [chartData, setChartData] = React.useState<TrafficPoint[]>([]);
  const [isLoading, setIsLoading] = React.useState(false);

  React.useEffect(() => {
    if (isMobile) {
      setTimeRange("15m");
    }
  }, [isMobile]);

  React.useEffect(() => {
    const load = async () => {
      setIsLoading(true);
      try {
        const bucketSeconds = bucketSecondsForRange(timeRange);
        const response = await fetch(`/api/stats/traffic-series?range=${timeRange}&bucket_seconds=${bucketSeconds}`, {
          cache: "no-store",
        });
        if (!response.ok) {
          return;
        }
        const payload = await response.json();
        setChartData(payload.data || []);
      } catch (error) {
        console.error("Failed to fetch traffic series:", error);
      } finally {
        setIsLoading(false);
      }
    };

    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, [timeRange]);

  const latest = chartData[chartData.length - 1];

  return (
    <Card className="@container/card">
      <CardHeader>
        <CardTitle>Aggregate Active Traffic</CardTitle>
        <CardDescription>Derived from per-subscriber SESSION_UPDATE deltas</CardDescription>
        <CardAction>
          <ToggleGroup
            type="single"
            value={timeRange}
            onValueChange={(value) => {
              if (value) {
                setTimeRange(value as RangeKey);
              }
            }}
            variant="outline"
            className="@[767px]/card:flex hidden *:data-[slot=toggle-group-item]:px-4!"
          >
            <ToggleGroupItem value="24h">Last 24h</ToggleGroupItem>
            <ToggleGroupItem value="6h">Last 6h</ToggleGroupItem>
            <ToggleGroupItem value="1h">Last 1h</ToggleGroupItem>
            <ToggleGroupItem value="15m">Last 15m</ToggleGroupItem>
          </ToggleGroup>
          <Select
            value={timeRange}
            onValueChange={(value) => {
              setTimeRange(value as RangeKey);
            }}
          >
            <SelectTrigger
              className="flex @[767px]/card:hidden w-40 **:data-[slot=select-value]:block **:data-[slot=select-value]:truncate"
              size="sm"
              aria-label="Select a value"
            >
              <SelectValue placeholder="Last 1 hour" />
            </SelectTrigger>
            <SelectContent className="rounded-xl">
              <SelectItem value="24h" className="rounded-lg">
                Last 24h
              </SelectItem>
              <SelectItem value="6h" className="rounded-lg">
                Last 6h
              </SelectItem>
              <SelectItem value="1h" className="rounded-lg">
                Last 1h
              </SelectItem>
              <SelectItem value="15m" className="rounded-lg">
                Last 15m
              </SelectItem>
            </SelectContent>
          </Select>
        </CardAction>
      </CardHeader>
      <CardContent className="px-2 pt-4 sm:px-6 sm:pt-6">
        <div className="text-sm text-muted-foreground mb-2">
          {isLoading && chartData.length === 0
            ? "Loading..."
            : latest
              ? `Current total: ${formatRate(latest.bps_total)}`
              : "No traffic samples yet"}
        </div>
        <ChartContainer config={chartConfig} className="aspect-auto h-62 w-full">
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id="fillIn" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-bps_in)" stopOpacity={0.9} />
                <stop offset="95%" stopColor="var(--color-bps_in)" stopOpacity={0.08} />
              </linearGradient>
              <linearGradient id="fillOut" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-bps_out)" stopOpacity={0.8} />
                <stop offset="95%" stopColor="var(--color-bps_out)" stopOpacity={0.08} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="ts"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              minTickGap={28}
              tickFormatter={(value) =>
                new Date(value).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })
              }
            />
            <ChartTooltip
              cursor={false}
              content={
                <ChartTooltipContent
                  labelFormatter={(value) =>
                    new Date(value).toLocaleString([], {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                    })
                  }
                  formatter={(value, name) => [formatRate(Number(value)), String(name)]}
                  indicator="dot"
                />
              }
            />
            <Area
              dataKey="bps_out"
              type="monotone"
              fill="url(#fillOut)"
              stroke="var(--color-bps_out)"
              strokeWidth={2}
            />
            <Area dataKey="bps_in" type="monotone" fill="url(#fillIn)" stroke="var(--color-bps_in)" strokeWidth={2} />
          </AreaChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
