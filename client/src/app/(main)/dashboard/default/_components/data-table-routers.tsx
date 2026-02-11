"use client";
"use no memo";

import * as React from "react";

import { DataTable } from "@/components/data-table/data-table";
import { DataTablePagination } from "@/components/data-table/data-table-pagination";
import { DataTableViewOptions } from "@/components/data-table/data-table-view-options";
import { useDataTableInstance } from "@/hooks/use-data-table-instance";
import { withDndColumn } from "@/components/data-table/table-utils";
import { Badge } from "@/components/ui/badge";

import { routersColumns } from "./routers-columns";
import type { Router } from "./routers-schema";

interface DataTableRoutersProps {
  data: Router[];
}

export function DataTableRouters({ data: initialData }: DataTableRoutersProps) {
  const [data, setData] = React.useState(() => initialData);
  const columns = withDndColumn(routersColumns);
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
            Identified access node routers and their active subscriber counts
          </p>
        </div>
        <div className="flex items-center gap-2">
          <DataTableViewOptions table={table} />
        </div>
      </div>
      <div className="overflow-hidden rounded-lg border">
        <DataTable dndEnabled table={table} columns={columns} onReorder={setData} />
      </div>
      <DataTablePagination table={table} />
    </div>
  );
}
