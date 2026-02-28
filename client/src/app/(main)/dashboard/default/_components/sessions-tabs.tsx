"use client";

import { useEffect, useState } from "react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import SessionsTable from "./sessions-table";
import SessionsHistoryTable from "./sessions-history-table";
import SessionsEventsTable from "./sessions-events-table";

export function SessionsTabs() {
  const [tab, setTab] = useState("active");

  useEffect(() => {
    function onSwitchTab(e: Event) {
      const detail = (e as CustomEvent<string>).detail;
      if (detail) setTab(detail);
    }
    window.addEventListener("switch-sessions-tab", onSwitchTab);
    return () => window.removeEventListener("switch-sessions-tab", onSwitchTab);
  }, []);

  return (
    <Tabs value={tab} onValueChange={setTab} id="sessions-tabs" className="w-full min-w-0">
      <TabsList>
        <TabsTrigger value="active">Active Sessions</TabsTrigger>
        <TabsTrigger value="history">Session History</TabsTrigger>
        <TabsTrigger value="events">Events</TabsTrigger>
      </TabsList>
      <TabsContent value="active" className="min-w-0">
        <SessionsTable />
      </TabsContent>
      <TabsContent value="history" className="min-w-0">
        <SessionsHistoryTable />
      </TabsContent>
      <TabsContent value="events" className="min-w-0">
        <SessionsEventsTable />
      </TabsContent>
    </Tabs>
  );
}
