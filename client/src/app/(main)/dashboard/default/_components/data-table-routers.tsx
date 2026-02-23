"use client";
"use no memo";

import * as React from "react";
import { Plus } from "lucide-react";

import { DataTable } from "@/components/data-table/data-table";
import { DataTablePagination } from "@/components/data-table/data-table-pagination";
import { DataTableViewOptions } from "@/components/data-table/data-table-view-options";
import { useDataTableInstance } from "@/hooks/use-data-table-instance";
import { withDndColumn } from "@/components/data-table/table-utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

import { createRoutersColumns } from "./routers-columns";
import type { Router } from "./routers-schema";

interface DataTableRoutersProps {
  data: Router[];
  onNewRouter?: () => void;
  onEdit?: (routerName: string) => void;
  onDelete?: (routerName: string) => void;
}

export function DataTableRouters({ data: initialData, onNewRouter, onEdit, onDelete }: DataTableRoutersProps) {
  const [data, setData] = React.useState(() => initialData);
  const columns = React.useMemo(
    () => withDndColumn(createRoutersColumns({ onEdit, onDelete })),
    [onEdit, onDelete],
  );
  const table = useDataTableInstance({
    data,
    columns,
    defaultPageSize: 100,
    getRowId: (row) => `${row.router_name}-${row.bng_id}`,
  });

  // Sync local state when initialData changes (from polling)
  React.useEffect(() => {
    setData(initialData);
  }, [initialData]);

  return (
    <div className="w-full flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-medium">Access Nodes</h3>
            <Badge variant="secondary">{data.length}</Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            Pre-configured access node routers and their status
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" onClick={onNewRouter}>
            <Plus className="mr-1 h-4 w-4" />
            New Router
          </Button>
          <DataTableViewOptions table={table} />
        </div>
      </div>
      <div className="overflow-x-auto rounded-lg border">
        <DataTable dndEnabled table={table} columns={columns} onReorder={setData} />
      </div>
      <DataTablePagination table={table} />
    </div>
  );
}
