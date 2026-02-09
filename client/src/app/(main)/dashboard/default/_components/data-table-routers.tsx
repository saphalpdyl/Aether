"use client";

import * as React from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable } from "@/components/data-table/data-table";
import { useDataTableInstance } from "@/hooks/use-data-table-instance";

import { routersColumns } from "./routers-columns";
import type { Router } from "./routers-schema";

interface DataTableRoutersProps {
  data: Router[];
}

export function DataTableRouters({ data: initialData }: DataTableRoutersProps) {
  const [data, setData] = React.useState<Router[]>(initialData);

  React.useEffect(() => {
    setData(initialData);
  }, [initialData]);

  const table = useDataTableInstance({
    data,
    columns: routersColumns,
    defaultPageSize: 100,
    getRowId: (row) => `${row.router_name}-${row.bng_id}`,
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Access Routers</CardTitle>
        <CardDescription>
          Identified access node routers and their active subscriber counts
        </CardDescription>
      </CardHeader>
      <CardContent>
        <DataTable table={table} columns={routersColumns} />
      </CardContent>
    </Card>
  );
}
