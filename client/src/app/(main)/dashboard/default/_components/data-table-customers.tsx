"use client";
"use no memo";

import * as React from "react";

import { flexRender } from "@tanstack/react-table";
import { DataTablePagination } from "@/components/data-table/data-table-pagination";
import { DataTableViewOptions } from "@/components/data-table/data-table-view-options";
import { useDataTableInstance } from "@/hooks/use-data-table-instance";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { customersColumns } from "./customers-columns";
import type { CustomerListing } from "./customers-schema";

interface DataTableCustomersProps {
  data: CustomerListing[];
  onRowClick?: (customer: CustomerListing) => void;
}

// Helper function to get row background class based on status
function getRowBackgroundClass(status: CustomerListing["status"]): string {
  switch (status) {
    case "online":
      return "bg-green-100 hover:bg-green-200 dark:bg-green-950/50 dark:hover:bg-green-950/70";
    case "recent":
      return "bg-orange-100 hover:bg-orange-200 dark:bg-orange-950/50 dark:hover:bg-orange-950/70";
    case "new":
      return "bg-blue-100 hover:bg-blue-200 dark:bg-blue-950/50 dark:hover:bg-blue-950/70";
    case "offline":
    default:
      return "hover:bg-muted/50";
  }
}

export function DataTableCustomers({ data: initialData, onRowClick }: DataTableCustomersProps) {
  const [data, setData] = React.useState(() => initialData);
  const table = useDataTableInstance({
    data,
    columns: customersColumns,
    defaultPageSize: 100,
  });

  React.useEffect(() => {
    setData(initialData);
  }, [initialData]);

  return (
    <div className="w-full flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-medium">Customers</h3>
            <Badge variant="secondary">{data.length}</Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            All customers and their online status
          </p>
        </div>
        <DataTableViewOptions table={table} />
      </div>
      <div className="overflow-hidden rounded-lg border">
        <Table>
          <TableHeader className="sticky top-0 z-10 bg-gray-50 dark:bg-gray-900">
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id} colSpan={header.colSpan}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  className={`cursor-pointer ${getRowBackgroundClass(row.original.status)}`}
                  onClick={() => onRowClick?.(row.original)}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={customersColumns.length} className="h-24 text-center">
                  No results.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      <DataTablePagination table={table} />
    </div>
  );
}
