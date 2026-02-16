"use client";

import { useState } from "react";
import { AlertTriangle, ChevronRight, Clock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface Alert {
  id: string;
  severity: "critical" | "major" | "minor";
  title: string;
  description: string;
  time: string;
  views: number;
}

const DUMMY_ALERTS: Alert[] = [
  {
    id: "1",
    severity: "critical",
    title: "Subscriber authentication failure – Router-02",
    description: "Simulated selection from bng-01",
    time: "1h ago",
    views: 1035,
  },
  {
    id: "2",
    severity: "major",
    title: "High CPU usage detected on bng-01 - YMb bash",
    description: "Simulated CPU spike on bng-01",
    time: "12 mon",
    views: 1035,
  },
  {
    id: "3",
    severity: "major",
    title: "Gateway down alert – No response from bng-02",
    description: "outrent response on bng-07",
    time: "12 mon",
    views: 1035,
  },
];

const ALERT_TAGS = [
  { id: "oss", label: "Oss", count: 4 },
  { id: "j45", label: "J45", count: 0 },
  { id: "triage", label: "Triage 10", count: 0 },
];

const severityConfig = {
  critical: {
    color: "text-red-600 dark:text-red-400",
    bg: "bg-red-500/10",
    icon: AlertTriangle,
  },
  major: {
    color: "text-orange-600 dark:text-orange-400",
    bg: "bg-orange-500/10",
    icon: AlertTriangle,
  },
  minor: {
    color: "text-yellow-600 dark:text-yellow-400",
    bg: "bg-yellow-500/10",
    icon: AlertTriangle,
  },
};

export function TopAlerts() {
  const [alerts] = useState<Alert[]>(DUMMY_ALERTS);

  return (
    <div className="rounded-lg border bg-card text-card-foreground shadow-sm overflow-hidden">
      <div className="p-6 pb-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Top Alerts</h3>
          <Button variant="ghost" size="sm" className="text-sm h-auto p-0 hover:bg-transparent">
            View All
            <ChevronRight className="size-4 ml-1" />
          </Button>
        </div>

        {/* Alerts List */}
        <div className="space-y-3">
          {alerts.map((alert) => {
            const config = severityConfig[alert.severity];
            const Icon = config.icon;

            return (
              <div
                key={alert.id}
                className="flex gap-3 p-3 rounded-lg border bg-card hover:bg-muted/50 cursor-pointer transition-colors"
              >
                <div className={`${config.bg} rounded-md p-2 h-fit`}>
                  <Icon className={`size-4 ${config.color}`} />
                </div>
                <div className="flex-1 min-w-0 space-y-1">
                  <div className="flex items-start justify-between gap-2">
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2">
                        <Badge
                          variant="outline"
                          className={`${config.color} border-current text-xs capitalize`}
                        >
                          {alert.severity}
                        </Badge>
                        <span className="text-xs text-muted-foreground">{alert.time}</span>
                      </div>
                      <p className="text-sm font-medium leading-tight">{alert.title}</p>
                    </div>
                    <div className="flex items-center gap-1 text-xs text-muted-foreground shrink-0">
                      <Clock className="size-3" />
                      {alert.views}
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground">{alert.description}</p>
                </div>
              </div>
            );
          })}
        </div>

        {/* Tags */}
        <div className="flex items-center gap-2 mt-4 pt-4 border-t">
          {ALERT_TAGS.map((tag) => (
            <Button
              key={tag.id}
              variant="outline"
              size="sm"
              className="h-7 text-xs"
            >
              {tag.label}
            </Button>
          ))}
          <Button variant="ghost" size="sm" className="h-7 text-xs ml-auto">
            View All
            <ChevronRight className="size-3 ml-1" />
          </Button>
        </div>
      </div>
    </div>
  );
}
