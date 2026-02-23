import type { ColumnDef } from "@tanstack/react-table";
import { Circle, Wifi } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { DataTableColumnHeader } from "@/components/data-table/data-table-column-header";

import type { CustomerListing } from "./customers-schema";

function formatDate(dateString: string | null): string {
  if (!dateString) return "—";
  return new Date(dateString).toLocaleString("en-US", {
    month: "numeric",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

const statusConfig = {
  online: {
    label: "Online",
    className: "bg-green-500/10 text-green-700 dark:text-green-400 border-green-500/20",
  },
  recent: {
    label: "Online last 24 hours",
    className: "bg-orange-500/10 text-orange-700 dark:text-orange-400 border-orange-500/20",
  },
  new: {
    label: "New",
    className: "bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/20",
  },
  offline: {
    label: "Offline",
    className: "bg-gray-500/10 text-gray-700 dark:text-gray-400 border-gray-500/20",
  },
} as const;

export const customersColumns: ColumnDef<CustomerListing>[] = [
  {
    id: "select",
    header: ({ table }) => (
      <Checkbox
        checked={table.getIsAllPageRowsSelected()}
        onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
        aria-label="Select all"
      />
    ),
    cell: ({ row }) => (
      <Checkbox
        checked={row.getIsSelected()}
        onCheckedChange={(value) => row.toggleSelected(!!value)}
        aria-label="Select row"
        onClick={(e) => e.stopPropagation()}
      />
    ),
    enableSorting: false,
    enableHiding: false,
  },
  {
    accessorKey: "name",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Customer" />,
    cell: ({ row }) => (
      <Link 
        href={`/dashboard/crm/customers/${row.original.id}`}
        className="font-medium text-blue-600 dark:text-blue-400 hover:underline"
        onClick={(e) => e.stopPropagation()}
      >
        {row.getValue("name")}
      </Link>
    ),
  },
  {
    accessorKey: "status",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Status" />,
    cell: ({ row }) => {
      const status = row.getValue("status") as keyof typeof statusConfig;
      const config = statusConfig[status] ?? statusConfig.offline;
      return (
        <Badge variant="outline" className={config.className}>
          <Circle className="size-2 mr-1 fill-current" />
          {config.label}
        </Badge>
      );
    },
  },
  {
    accessorKey: "email",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Email" />,
    cell: ({ row }) => (
      <a href={`mailto:${row.getValue("email")}`} className="text-sm text-blue-600 dark:text-blue-400 hover:underline">
        {row.getValue("email") ?? "—"}
      </a>
    ),
  },
  {
    id: "location",
    header: ({ column }) => <DataTableColumnHeader column={column} title="City / State" />,
    accessorFn: (row) => [row.city, row.state].filter(Boolean).join(", ") || null,
    cell: ({ getValue }) => <span className="text-sm">{(getValue() as string | null) ?? "—"}</span>,
  },
  {
    id: "service",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Service" />,
    cell: ({ row }) => {
      // You may need to adjust this based on your actual data structure
      const serviceCount = row.getValue("service_count") as number;
      return (
        <div className="flex items-center gap-1.5">
          <Wifi className="size-3.5 text-muted-foreground" />
          <span className="text-sm">{serviceCount > 0 ? `${serviceCount} service${serviceCount > 1 ? 's' : ''}` : '—'}</span>
        </div>
      );
    },
  },
  {
    accessorKey: "service_count",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Port" />,
    cell: ({ row }) => <span className="text-sm">{row.getValue("service_count") || "—"}</span>,
  },
  {
    accessorKey: "active_sessions",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Active Sessions" />,
    cell: ({ row }) => {
      const sessions = row.getValue("active_sessions") as number;
      return <span className="text-sm font-medium">{sessions}</span>;
    },
  },
  {
    accessorKey: "ip_assignments",
    header: ({ column }) => <DataTableColumnHeader column={column} title="IP Assignments" />,
    cell: ({ row }) => {
      const ip = row.getValue("ip_assignments") as string | null;
      return <span className="text-sm font-mono">{ip || "—"}</span>;
    },
  },
  {
    id: "usage",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Usage" />,
    cell: () => <span className="text-sm">—</span>,
  },
];
