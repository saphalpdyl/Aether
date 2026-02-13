"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { routerSchema } from "./routers-schema";
import type { Router } from "./routers-schema";
import { DataTableRouters } from "./data-table-routers";
import { RouterCreateDialog } from "./router-create-dialog";

export default function RoutersTable() {
  const [routers, setRouters] = useState<Router[]>([]);
  const [createOpen, setCreateOpen] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const response = await fetch("/api/routers");
      if (response.ok) {
        const result = await response.json();
        const validatedRouters = result.data
          .map((router: unknown) => {
            try {
              return routerSchema.parse(router);
            } catch {
              return null;
            }
          })
          .filter((router: Router | null): router is Router => router !== null);
        setRouters(validatedRouters);
      }
    } catch (error) {
      console.error("Failed to fetch routers:", error);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 2000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleEdit = useCallback(
    async (routerName: string) => {
      const router = routers.find((r) => r.router_name === routerName);
      if (!router) return;

      const newGiaddr = prompt("Gateway IP (giaddr):", router.giaddr);
      if (newGiaddr === null) return;
      const newBngId = prompt("BNG ID:", router.bng_id ?? "");
      if (newBngId === null) return;

      try {
        const response = await fetch(`/api/routers/${encodeURIComponent(routerName)}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            giaddr: newGiaddr || undefined,
            bng_id: newBngId || undefined,
          }),
        });
        if (!response.ok) {
          const err = await response.json().catch(() => ({}));
          throw new Error(err.error || `Failed (${response.status})`);
        }
        toast.success(`Router "${routerName}" updated`);
        fetchData();
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to update router");
      }
    },
    [routers, fetchData],
  );

  const handleDelete = useCallback(
    async (routerName: string) => {
      if (!confirm(`Delete router "${routerName}"?`)) return;
      try {
        const response = await fetch(`/api/routers/${encodeURIComponent(routerName)}`, {
          method: "DELETE",
        });
        if (!response.ok) {
          const err = await response.json().catch(() => ({}));
          throw new Error(err.error || `Failed (${response.status})`);
        }
        toast.success(`Router "${routerName}" deleted`);
        fetchData();
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to delete router");
      }
    },
    [fetchData],
  );

  return (
    <>
      <DataTableRouters
        data={routers}
        onNewRouter={() => setCreateOpen(true)}
        onEdit={handleEdit}
        onDelete={handleDelete}
      />
      <RouterCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={fetchData}
      />
    </>
  );
}
