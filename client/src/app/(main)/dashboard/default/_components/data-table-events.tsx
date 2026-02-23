"use client";
"use no memo";

import * as React from "react";

import type { z } from "zod";

import { Badge } from "@/components/ui/badge";
import { useDataTableInstance } from "@/hooks/use-data-table-instance";

import { DataTable as DataTableNew } from "../../../../../components/data-table/data-table";
import { DataTablePagination } from "../../../../../components/data-table/data-table-pagination";
import { DataTableViewOptions } from "../../../../../components/data-table/data-table-view-options";
import { eventsColumns } from "./events-columns";
import type { sessionEventSchema } from "./events-schema";

export function DataTable({ data: initialData }: { data: z.infer<typeof sessionEventSchema>[] }) {
  const [data, setData] = React.useState(() => initialData);
  const columns = eventsColumns; // No DnD wrapper
  const table = useDataTableInstance({ 
    data, 
    columns, 
    getRowId: (row) => `${row.bng_id}-${row.bng_instance_id}-${row.seq}` 
  });

  // Sync local state when initialData changes (from polling)
  React.useEffect(() => {
    setData(initialData);
  }, [initialData]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-medium">Session Events</h3>
          <Badge variant="secondary">{data.length}</Badge>
        </div>
        <DataTableViewOptions table={table} />
      </div>
      <div className="overflow-x-auto rounded-lg border">
        <DataTableNew table={table} columns={columns} />
      </div>
      <DataTablePagination table={table} />
    </div>
  );
}
