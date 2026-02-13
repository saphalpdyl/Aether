import type { ColumnDef } from "@tanstack/react-table";
import { CircleCheck, Clock, Sparkles, CircleMinus } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { DataTableColumnHeader } from "@/components/data-table/data-table-column-header";

import type { CustomerListing } from "./customers-schema";

function formatDate(dateString: string | null): string {
  if (!dateString) return "\u2014";
  return new Date(dateString).toLocaleString();
}

const statusConfig = {
  online: {
    label: "Online",
    icon: CircleCheck,
    className: "bg-green-600 text-white",
  },
  recent: {
    label: "Online 24h",
    icon: Clock,
    className: "bg-blue-600 text-white",
  },
  new: {
    label: "New",
    icon: Sparkles,
    className: "bg-purple-600 text-white",
  },
  offline: {
    label: "Offline",
    icon: CircleMinus,
    className: "bg-muted text-muted-foreground",
  },
} as const;

export const customersColumns: ColumnDef<CustomerListing>[] = [
  {
    accessorKey: "status",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Status" />,
    cell: ({ row }) => {
      const status = row.getValue("status") as keyof typeof statusConfig;
      const config = statusConfig[status] ?? statusConfig.offline;
      const Icon = config.icon;
      return (
        <Badge className={config.className}>
          <Icon className="mr-1 h-3 w-3" />
          {config.label}
        </Badge>
      );
    },
  },
  {
    accessorKey: "name",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Name" />,
    cell: ({ row }) => <span className="font-medium">{row.getValue("name")}</span>,
  },
  {
    accessorKey: "email",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Email" />,
    cell: ({ row }) => <span className="text-sm">{row.getValue("email") ?? "\u2014"}</span>,
  },
  {
    id: "location",
    header: ({ column }) => <DataTableColumnHeader column={column} title="City / State" />,
    accessorFn: (row) => [row.city, row.state].filter(Boolean).join(", ") || null,
    cell: ({ getValue }) => <span className="text-sm">{(getValue() as string | null) ?? "\u2014"}</span>,
  },
  {
    accessorKey: "service_count",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Services" />,
    cell: ({ row }) => <span className="text-sm font-semibold">{row.getValue("service_count")}</span>,
  },
  {
    accessorKey: "active_sessions",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Active Sessions" />,
    cell: ({ row }) => <span className="text-sm font-semibold">{row.getValue("active_sessions")}</span>,
  },
  {
    accessorKey: "created_at",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Created At" />,
    cell: ({ row }) => (
      <span className="text-sm whitespace-nowrap">{formatDate(row.getValue("created_at"))}</span>
    ),
  },
];
