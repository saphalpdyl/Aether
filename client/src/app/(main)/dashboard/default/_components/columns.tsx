import type { ColumnDef } from "@tanstack/react-table";
import { ArrowDown, ArrowUp, CircleCheck, XCircle } from "lucide-react";
import type { z } from "zod";

import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";

import { DataTableColumnHeader } from "../../../../../components/data-table/data-table-column-header";
import { DisconnectButton } from "./disconnect-button";
import type { sessionSchema } from "./schema";

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleString();
}

export const dashboardColumns: ColumnDef<z.infer<typeof sessionSchema>>[] = [
  {
    id: "select",
    header: ({ table }) => (
      <div className="flex items-center justify-center">
        <Checkbox
          checked={table.getIsAllPageRowsSelected() || (table.getIsSomePageRowsSelected() && "indeterminate")}
          onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
          aria-label="Select all"
        />
      </div>
    ),
    cell: ({ row }) => (
      <div className="flex items-center justify-center">
        <Checkbox
          checked={row.getIsSelected()}
          onCheckedChange={(value) => row.toggleSelected(!!value)}
          aria-label="Select row"
        />
      </div>
    ),
    enableSorting: false,
    enableHiding: false,
  },
  {
    id: "actions",
    header: () => <div className="text-center">Actions</div>,
    cell: ({ row }) => (
      <div className="flex items-center justify-center">
        <DisconnectButton
          sessionId={row.original.session_id}
          username={row.original.username}
        />
      </div>
    ),
    enableSorting: false,
    enableHiding: false,
  },
  {
    accessorKey: "status",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Status" />,
    cell: ({ row }) => {
        const status = String(row.getValue("status") ?? "");
        const isActive = status.toUpperCase() === "ACTIVE";
        return (
          <Badge variant={isActive ? "default" : "secondary"}>
            {isActive ? <CircleCheck className="mr-1 h-3 w-3" /> : <XCircle className="mr-1 h-3 w-3" />}
            {status}
          </Badge>
        );
    },
  },
  {
    accessorKey: "username",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Username" />,
    cell: ({ row }) => <div className="font-medium">{row.getValue("username")}</div>,
  },
  {
    accessorKey: "ip_address",
    header: ({ column }) => <DataTableColumnHeader column={column} title="IP Address" />,
    cell: ({ row }) => <div className="font-mono text-sm">{row.getValue("ip_address")}</div>,
  },
  {
    accessorKey: "mac_address",
    header: ({ column }) => <DataTableColumnHeader column={column} title="MAC Address" />,
    cell: ({ row }) => <div className="font-mono text-sm">{row.getValue("mac_address")}</div>,
  },
  {
    accessorKey: "start_time",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Start Time" />,
    cell: ({ row }) => (
      <div className="text-sm whitespace-nowrap">{formatDate(row.getValue("start_time"))}</div>
    ),
  },
  {
    accessorKey: "input_octets",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Download" />,
    cell: ({ row }) => (
      <div className="flex items-center gap-1 text-sm">
        <ArrowDown className="h-3 w-3 text-blue-500" />
        <span>{formatBytes(Number(row.getValue("input_octets") ?? 0))}</span>
      </div>
    ),
  },
  {
    accessorKey: "output_octets",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Upload" />,
    cell: ({ row }) => (
      <div className="flex items-center gap-1 text-sm">
        <ArrowUp className="h-3 w-3 text-green-500" />
        <span>{formatBytes(Number(row.getValue("output_octets") ?? 0))}</span>
      </div>
    ),
  },
  {
    accessorKey: "auth_state",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Auth State" />,
    cell: ({ row }) => {
      const authState = String(row.getValue("auth_state") ?? "").toLowerCase();
      const isRejected = authState === "rejected";
      
      return (
        <Badge 
          variant={isRejected ? "destructive" : "outline"} 
          className="capitalize"
        >
          {row.getValue("auth_state")}
        </Badge>
      );
    },
  },
  {
    accessorKey: "bng_id",
    header: ({ column }) => <DataTableColumnHeader column={column} title="BNG ID" />,
    cell: ({ row }) => <div className="text-sm">{row.getValue("bng_id")}</div>,
  },
  {
    accessorKey: "nas_ip",
    header: ({ column }) => <DataTableColumnHeader column={column} title="NAS IP" />,
    cell: ({ row }) => <div className="font-mono text-sm">{row.getValue("nas_ip")}</div>,
  },
  {
    accessorKey: "circuit_id",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Circuit ID" />,
    cell: ({ row }) => <div className="text-sm truncate max-w-37.5">{row.getValue("circuit_id")}</div>,
  },
  {
    accessorKey: "remote_id",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Remote ID" />,
    cell: ({ row }) => <div className="text-sm truncate max-w-37.5">{row.getValue("remote_id")}</div>,
  },
  {
    accessorKey: "input_packets",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Input Packets" />,
    cell: ({ row }) => (
      <div className="flex items-center gap-1 text-sm">
        <ArrowDown className="h-3 w-3 text-blue-500/70" />
        <span>{Number(row.getValue("input_packets") ?? 0).toLocaleString()}</span>
      </div>
    ),
  },
  {
    accessorKey: "output_packets",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Output Packets" />,
    cell: ({ row }) => (
      <div className="flex items-center gap-1 text-sm">
        <ArrowUp className="h-3 w-3 text-green-500/70" />
        <span>{Number(row.getValue("output_packets") ?? 0).toLocaleString()}</span>
      </div>
    ),
  },
  {
    accessorKey: "last_update",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Last Update" />,
    cell: ({ row }) => (
      <div className="text-sm whitespace-nowrap">{formatDate(row.getValue("last_update"))}</div>
    ),
  },
  {
    accessorKey: "session_id",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Session ID" />,
    cell: ({ row }) => (
      <div className="font-mono text-xs truncate max-w-50" title={row.getValue("session_id")}>
        {row.getValue("session_id")}
      </div>
    ),
  },
  {
    accessorKey: "bng_instance_id",
    header: ({ column }) => <DataTableColumnHeader column={column} title="BNG Instance ID" />,
    cell: ({ row }) => (
      <div className="font-mono text-xs truncate max-w-50" title={row.getValue("bng_instance_id")}>
        {row.getValue("bng_instance_id")}
      </div>
    ),
  },
];
