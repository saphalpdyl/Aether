"use client";
"use no memo";

import * as React from "react";

import { Plus } from "lucide-react";
import type { z } from "zod";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useDataTableInstance } from "@/hooks/use-data-table-instance";

import { DataTable as DataTableNew } from "../../../../../components/data-table/data-table";
import { DataTablePagination } from "../../../../../components/data-table/data-table-pagination";
import { DataTableViewOptions } from "../../../../../components/data-table/data-table-view-options";
import { withDndColumn } from "../../../../../components/data-table/table-utils";
import { historyColumns } from "./history-columns";
import type { sessionHistorySchema } from "./history-schema";

export function DataTable({ data: initialData }: { data: z.infer<typeof sessionHistorySchema>[] }) {
  const [data, setData] = React.useState(() => initialData);
  const columns = withDndColumn(historyColumns);
  const table = useDataTableInstance({ data, columns, getRowId: (row) => row.session_id.toString() });

  // Sync local state when initialData changes (from polling)
  React.useEffect(() => {
    setData(initialData);
  }, [initialData]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-medium">Session History</h3>
          <Badge variant="secondary">{data.length}</Badge>
        </div>
        <DataTableViewOptions table={table} />
      </div>
      <div className="overflow-hidden rounded-lg border">
        <DataTableNew table={table} columns={columns} />
      </div>
      <DataTablePagination table={table} />
    </div>
  );
}
