"use client";

import * as React from "react";

import { DataTable } from "./data-table";
import { sessionSchema, type Session } from "./schema";

export default function SessionsTable() {
  const [data, setData] = React.useState<Session[]>([]);

  React.useEffect(() => {
    let mounted = true;

    async function fetchData() {
      try {
        const res = await fetch("/api/sessions/active", { cache: "no-store" });
        if (!res.ok) return;
        const json = await res.json();
        console.log(json)
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
                  // eslint-disable-next-line no-console
                  console.warn("Session parse failed", e, parsed);
                  return null;
                }
              })
              .filter(Boolean)
          : [];

        if (mounted) setData(items as Session[]);
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error(err);
      }
    }

    fetchData();
    const id = setInterval(fetchData, 2000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, []);

  return <DataTable data={data} />;
}
