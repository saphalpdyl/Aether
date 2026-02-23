"use client";

import * as React from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Activity } from "lucide-react";

interface SessionEvent {
  ts: string;
  event_type: string;
  input_octets: number;
  output_octets: number;
  session_id: string;
  status: string | null;
  auth_state: string | null;
  username: string | null;
  circuit_id: string;
  remote_id: string;
}

interface ActivityPeriod {
  start: Date;
  end: Date;
  status: "active" | "idle" | "offline";
}

interface ServiceTimeline {
  serviceId: string;
  serviceLabel: string;
  periods: ActivityPeriod[];
}

interface CustomerSessionActivityChartProps {
  customerId: string;
}

export default function CustomerSessionActivityChart({ customerId }: CustomerSessionActivityChartProps) {
  const [events, setEvents] = React.useState<SessionEvent[]>([]);
  const [serviceTimelines, setServiceTimelines] = React.useState<ServiceTimeline[]>([]);
  const [loading, setLoading] = React.useState(true);

  // Fetch customer events
  React.useEffect(() => {
    let mounted = true;

    async function fetchData() {
      try {
        const res = await fetch(`/api/customers/${customerId}/events`, { cache: "no-store" });
        if (!res.ok) return;
        const json = await res.json();
        
        if (mounted && Array.isArray(json.data)) {
          setEvents(json.data);
          setLoading(false);
        }
      } catch (err) {
        console.error("Error fetching customer events:", err);
        setLoading(false);
      }
    }

    fetchData();
    const id = setInterval(fetchData, 10000); // Refresh every 10 seconds
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, [customerId]);

  // Process events into activity periods per service
  React.useEffect(() => {
    if (events.length === 0) return;

    // Group events by username (which represents a unique service)
    const eventsByService = new Map<string, SessionEvent[]>();
    
    events.forEach(event => {
      const serviceKey = event.username || event.circuit_id || "unknown";
      if (!eventsByService.has(serviceKey)) {
        eventsByService.set(serviceKey, []);
      }
      eventsByService.get(serviceKey)!.push(event);
    });

    // Process each service's events into timelines
    const timelines: ServiceTimeline[] = [];

    eventsByService.forEach((serviceEvents, serviceKey) => {
      const periods: ActivityPeriod[] = [];
      const sortedEvents = [...serviceEvents].sort((a, b) => 
        new Date(a.ts).getTime() - new Date(b.ts).getTime()
      );
      
      for (let index = 0; index < sortedEvents.length; index++) {
        const event = sortedEvents[index];
        const eventTime = new Date(event.ts);
        
        if (event.event_type === "SESSION_START") {
          // Start a new active period (assume active on start)
          periods.push({
            start: eventTime,
            end: eventTime,
            status: "active"
          });
        } else if (event.event_type === "SESSION_UPDATE" || event.event_type === "POLICY_APPLY") {
          const lastPeriod = periods[periods.length - 1];
          
          // For POLICY_APPLY with REJECTED auth_state, treat as offline
          if (event.event_type === "POLICY_APPLY" && event.auth_state?.toUpperCase() === "REJECTED") {
            // End the current period if it exists and is not already offline
            if (lastPeriod && lastPeriod.status !== "offline") {
              lastPeriod.end = eventTime;
            }
            
            // Check if there's a next event - if not or if it's not a START, add offline period
            const nextEvent = sortedEvents[index + 1];
            if (nextEvent) {
              const nextEventTime = new Date(nextEvent.ts);
              // Add offline period until next event (unless it's a START)
              if (nextEvent.event_type !== "SESSION_START") {
                periods.push({
                  start: eventTime,
                  end: nextEventTime,
                  status: "offline"
                });
              }
            } else {
              // No more events - offline until now
              periods.push({
                start: eventTime,
                end: new Date(),
                status: "offline"
              });
            }
          } else {
            // Regular SESSION_UPDATE or POLICY_APPLY with authorized state
            // Determine status from the event's status field
            const eventStatus = event.status?.toUpperCase();
            const newStatus: "active" | "idle" = eventStatus === "IDLE" ? "idle" : "active";
            
            if (lastPeriod && lastPeriod.status !== "offline") {
              // If status changed, start new period
              if (newStatus !== lastPeriod.status) {
                periods.push({
                  start: lastPeriod.end,
                  end: eventTime,
                  status: newStatus
                });
              } else {
                // Continue current period
                lastPeriod.end = eventTime;
              }
            } else {
              // Start new period if none exists
              periods.push({
                start: eventTime,
                end: eventTime,
                status: newStatus
              });
            }
          }
        } else if (event.event_type === "SESSION_STOP") {
          const lastPeriod = periods[periods.length - 1];
          if (lastPeriod && lastPeriod.status !== "offline") {
            lastPeriod.end = eventTime;
          }
          
          // Check if there's a next event - if not or if it's not a START, add offline period
          const nextEvent = sortedEvents[index + 1];
          if (nextEvent) {
            const nextEventTime = new Date(nextEvent.ts);
            if (nextEvent.event_type !== "SESSION_START") {
              // Add offline period until next event
              periods.push({
                start: eventTime,
                end: nextEventTime,
                status: "offline"
              });
            }
          } else {
            // No more events - offline until now
            periods.push({
              start: eventTime,
              end: new Date(),
              status: "offline"
            });
          }
        }
      }

      // If there's still an active/idle period, extend it to now
      const lastPeriod = periods[periods.length - 1];
      if (lastPeriod && lastPeriod.status !== "offline") {
        lastPeriod.end = new Date();
      }

      // Create a readable label from circuit_id and remote_id
      const firstEvent = sortedEvents[0];
      const serviceLabel = `${firstEvent.remote_id} - ${firstEvent.circuit_id}`.substring(0, 40);

      timelines.push({
        serviceId: serviceKey,
        serviceLabel,
        periods
      });
    });

    setServiceTimelines(timelines);
  }, [events]);

  // Calculate common timeline bounds across all services
  const getCommonTimelineBounds = () => {
    const now = new Date();
    const oneDayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    
    // Find the earliest start time across all services
    let earliestStart = now;
    serviceTimelines.forEach(timeline => {
      timeline.periods.forEach(period => {
        if (period.start.getTime() < earliestStart.getTime()) {
          earliestStart = period.start;
        }
      });
    });

    // Use the earlier of: 24h ago or the earliest event
    const timelineStart = earliestStart.getTime() < oneDayAgo.getTime() 
      ? oneDayAgo 
      : earliestStart;
    
    return {
      start: timelineStart,
      end: now,
      duration: now.getTime() - timelineStart.getTime()
    };
  };

  // Calculate timeline dimensions for a specific service using common bounds
  const getTimelineDataForService = (periods: ActivityPeriod[], bounds: { start: Date; end: Date; duration: number }) => {
    if (periods.length === 0) return null;

    return periods.map(period => {
      const start = Math.max(period.start.getTime(), bounds.start.getTime());
      const end = Math.min(period.end.getTime(), bounds.end.getTime());
      const leftPercent = ((start - bounds.start.getTime()) / bounds.duration) * 100;
      const widthPercent = ((end - start) / bounds.duration) * 100;

      return {
        ...period,
        leftPercent,
        widthPercent
      };
    }).filter(p => p.widthPercent > 0);
  };

  // Calculate aggregate stats across all services
  const getAllPeriods = () => {
    return serviceTimelines.flatMap(timeline => timeline.periods);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "active":
        return "bg-green-500";
      case "idle":
        return "bg-orange-500";
      case "offline":
        return "bg-transparent";
      default:
        return "bg-gray-200";
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case "active":
        return "Active";
      case "idle":
        return "Idle";
      case "offline":
        return "Offline";
      default:
        return "Unknown";
    }
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Session Activity Timeline
          </CardTitle>
          <CardDescription>Loading activity data...</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-24 bg-muted animate-pulse rounded" />
        </CardContent>
      </Card>
    );
  }

  if (serviceTimelines.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Session Activity Timeline
          </CardTitle>
          <CardDescription>Last 24 hours of session activity</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-center text-muted-foreground py-8">No session activity data available</p>
        </CardContent>
      </Card>
    );
  }

  const allPeriods = getAllPeriods();
  const commonBounds = getCommonTimelineBounds();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="h-5 w-5" />
          Session Activity Timeline
        </CardTitle>
        <CardDescription>
          Last 24 hours of session activity
          {serviceTimelines.length > 1 && ` (${serviceTimelines.length} services)`}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Legend */}
        <div className="flex items-center gap-4 text-sm">
          <div className="flex items-center gap-2">
            <div 
              className="w-4 h-4 rounded relative overflow-hidden"
              style={{
                backgroundColor: "rgb(34 197 94)", // green-500
                backgroundImage: "repeating-linear-gradient(45deg, transparent, transparent 2px, rgba(255,255,255,0.3) 2px, rgba(255,255,255,0.3) 4px)",
              }}
            />
            <span>Active</span>
          </div>
          <div className="flex items-center gap-2">
            <div 
              className="w-4 h-4 rounded relative overflow-hidden"
              style={{
                backgroundColor: "rgb(249 115 22)", // orange-500
                backgroundImage: "repeating-linear-gradient(45deg, transparent, transparent 2px, rgba(255,255,255,0.3) 2px, rgba(255,255,255,0.3) 4px)",
              }}
            />
            <span>Idle</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 border-2 border-dashed border-gray-300 rounded" />
            <span>Offline</span>
          </div>
        </div>

        {/* Timelines - one per service */}
        <div className="space-y-4">
          {serviceTimelines.map((timeline) => {
            const timelineData = getTimelineDataForService(timeline.periods, commonBounds);
            if (!timelineData) return null;

            return (
              <div key={timeline.serviceId} className="space-y-2">
                {/* Service label */}
                {serviceTimelines.length > 1 && (
                  <div className="text-sm font-medium text-muted-foreground truncate">
                    {timeline.serviceLabel}
                  </div>
                )}
                
                {/* Timeline bar */}
                <div className="relative w-full">
                  <div className="relative h-12 bg-gray-100 dark:bg-gray-900 rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-700 overflow-hidden">
                    {timelineData.map((period, index) => (
                      <div
                        key={index}
                        className={`absolute h-full transition-all ${period.status === "offline" ? "bg-transparent" : ""}`}
                        style={{
                          left: `${period.leftPercent}%`,
                          width: `${period.widthPercent}%`,
                          ...(period.status === "active" && {
                            backgroundColor: "rgb(34 197 94)", // green-500
                            backgroundImage: "repeating-linear-gradient(45deg, transparent, transparent 4px, rgba(255,255,255,0.3) 4px, rgba(255,255,255,0.3) 8px)",
                          }),
                          ...(period.status === "idle" && {
                            backgroundColor: "rgb(249 115 22)", // orange-500
                            backgroundImage: "repeating-linear-gradient(45deg, transparent, transparent 4px, rgba(255,255,255,0.3) 4px, rgba(255,255,255,0.3) 8px)",
                          }),
                        }}
                        title={`${getStatusLabel(period.status)}: ${period.start.toLocaleTimeString()} - ${period.end.toLocaleTimeString()}`}
                      />
                    ))}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Time markers */}
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>24h ago</span>
          <span>12h ago</span>
          <span>Now</span>
        </div>

        {/* Aggregate Stats */}
        <div className="grid grid-cols-3 gap-4 pt-4 border-t">
          <div>
            <p className="text-xs text-muted-foreground">Total Active Time</p>
            <p className="text-lg font-semibold text-green-600">
              {Math.round(
                allPeriods
                  .filter(p => p.status === "active")
                  .reduce((acc, p) => acc + (p.end.getTime() - p.start.getTime()), 0) / 1000 / 60
              )} min
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Total Idle Time</p>
            <p className="text-lg font-semibold text-orange-400">
              {Math.round(
                allPeriods
                  .filter(p => p.status === "idle")
                  .reduce((acc, p) => acc + (p.end.getTime() - p.start.getTime()), 0) / 1000 / 60
              )} min
            </p>
          </div>
          
        </div>
      </CardContent>
    </Card>
  );
}
