import type { ColumnDef } from "@tanstack/react-table";

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
    className: "bg-green-500 text-white hover:bg-green-600",
  },
  recent: {
    label: "Online 24h",
    className: "bg-orange-500 text-white hover:bg-orange-600",
  },
  new: {
    label: "New",
    className: "bg-blue-500 text-white hover:bg-blue-600",
  },
  offline: {
    label: "Offline",
    className: "bg-gray-500 text-white hover:bg-gray-600",
  },
} as const;

export const customersColumns: ColumnDef<CustomerListing>[] = [
  {
    accessorKey: "name",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Name" />,
    cell: ({ row }) => <span className="font-medium">{row.getValue("name")}</span>,
  },
  {
    accessorKey: "status",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Status" />,
    cell: ({ row }) => {
      const status = row.getValue("status") as keyof typeof statusConfig;
      const config = statusConfig[status] ?? statusConfig.offline;
      return (
        <Badge className={`${config.className} rounded-none text-md font-bold`}>
          {config.label}
        </Badge>
      );
    },
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
