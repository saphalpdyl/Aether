"use client";

import * as React from "react";

import { DataTable } from "../../../../default/_components/data-table";
import { sessionSchema, type Session } from "../../../../default/_components/schema";

interface CustomerSessionsTableProps {
  customerId: string;
}

export default function CustomerSessionsTable({ customerId }: CustomerSessionsTableProps) {
  const [data, setData] = React.useState<Session[]>([]);

  // Fetch customer's active sessions
  React.useEffect(() => {
    let mounted = true;

    async function fetchData() {
      try {
        const res = await fetch(`/api/customers/${customerId}/sessions`, { cache: "no-store" });
        if (!res.ok) return;
        const json = await res.json();
        
        const items = Array.isArray(json.data)
          ? json.data
              .map((s: any) => {
                // normalize numeric fields that may come back as strings
                const parsed = {
                  ...s,
                  input_octets: s.input_octets === undefined ? 0 : Number(s.input_octets),
                  output_octets: s.output_octets === undefined ? 0 : Number(s.output_octets),
                  input_packets: s.input_packets === undefined ? 0 : Number(s.input_packets),
                  output_packets: s.output_packets === undefined ? 0 : Number(s.output_packets),
                };
                try {
                  return sessionSchema.parse(parsed) as Session;
                } catch (e) {
                  // validation failed for this row — skip it
                  console.warn("Session parse failed", e, parsed);
                  return null;
                }
              })
              .filter(Boolean)
          : [];

        if (mounted) setData(items as Session[]);
      } catch (err) {
        console.error("Error fetching customer sessions:", err);
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
