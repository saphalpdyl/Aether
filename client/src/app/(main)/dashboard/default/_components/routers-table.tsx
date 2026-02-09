"use client";

import { useEffect, useState } from "react";
import { routerSchema } from "./routers-schema";
import type { Router } from "./routers-schema";
import { DataTableRouters } from "./data-table-routers";

export default function RoutersTable() {
  const [routers, setRouters] = useState<Router[]>([]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        console.log("Fetching routers...");
        const response = await fetch("/api/routers");
        console.log("Routers response status:", response.status);
        if (response.ok) {
          const result = await response.json();
          console.log("Routers data received:", result);
          const validatedRouters = result.data
            .map((router: unknown) => {
              try {
                return routerSchema.parse(router);
              } catch (error) {
                console.warn("Failed to validate router:", error);
                return null;
              }
            })
            .filter((router: Router | null): router is Router => router !== null);

          setRouters(validatedRouters);
        } else {
          console.error("Failed to fetch routers, status:", response.status);
        }
      } catch (error) {
        console.error("Failed to fetch routers:", error);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 2000);

    return () => clearInterval(interval);
  }, []);


  return <DataTableRouters data={routers} />;
}
