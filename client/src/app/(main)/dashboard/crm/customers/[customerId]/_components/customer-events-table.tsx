"use client";

import * as React from "react";

import { DataTable } from "../../../../default/_components/data-table-events";
import { sessionEventSchema, type SessionEvent } from "../../../../default/_components/events-schema";

interface CustomerEventsTableProps {
  customerId: string;
}

export default function CustomerEventsTable({ customerId }: CustomerEventsTableProps) {
  const [data, setData] = React.useState<SessionEvent[]>([]);

  // Fetch customer's events
  React.useEffect(() => {
    let mounted = true;

    async function fetchData() {
      try {
        const res = await fetch(`/api/customers/${customerId}/events`, { cache: "no-store" });
        if (!res.ok) return;
        const json = await res.json();
        
        const items = Array.isArray(json.data)
          ? json.data
              .map((s: any) => {
                // normalize numeric fields that may come back as strings
                const parsed = {
                  ...s,
                  seq: s.seq === undefined ? 0 : Number(s.seq),
                  input_octets: s.input_octets === undefined ? 0 : Number(s.input_octets),
                  output_octets: s.output_octets === undefined ? 0 : Number(s.output_octets),
                  input_packets: s.input_packets === undefined ? 0 : Number(s.input_packets),
                  output_packets: s.output_packets === undefined ? 0 : Number(s.output_packets),
                };
                try {
                  return sessionEventSchema.parse(parsed) as SessionEvent;
                } catch (e) {
                  // validation failed for this row — skip it
                  console.warn("[Events] Event parse failed", e, parsed);
                  return null;
                }
              })
              .filter(Boolean)
          : [];

        if (mounted) setData(items as SessionEvent[]);
      } catch (err) {
        console.error("[Events] Fetch error:", err);
      }
    }

    fetchData();
    const id = setInterval(fetchData, 2000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, [customerId]);

  return <DataTable data={data} />;
}
