import type { ColumnDef } from "@tanstack/react-table";
import { ArrowDown, ArrowUp, Activity, PlayCircle, StopCircle, RefreshCw } from "lucide-react";
import type { z } from "zod";

import { Badge } from "@/components/ui/badge";

import { DataTableColumnHeader } from "../../../../../components/data-table/data-table-column-header";
import type { sessionEventSchema } from "./events-schema";

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

function getEventIcon(eventType: string) {
  switch (eventType) {
    case "SESSION_START":
      return <PlayCircle className="h-3 w-3" />;
    case "SESSION_STOP":
      return <StopCircle className="h-3 w-3" />;
    case "SESSION_UPDATE":
      return <RefreshCw className="h-3 w-3" />;
    case "POLICY_APPLY":
      return <Activity className="h-3 w-3" />;
    default:
      return null;
  }
}

function getEventVariant(eventType: string): "default" | "secondary" | "destructive" | "outline" {
  switch (eventType) {
    case "SESSION_START":
      return "default";
    case "SESSION_STOP":
      return "destructive";
    case "SESSION_UPDATE":
      return "secondary";
    case "POLICY_APPLY":
      return "outline";
    default:
      return "outline";
  }
}

export const eventsColumns: ColumnDef<z.infer<typeof sessionEventSchema>>[] = [
  {
    accessorKey: "event_type",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Event Type" />,
    cell: ({ row }) => {
      const eventType = String(row.getValue("event_type") ?? "");
      return (
        <Badge variant={getEventVariant(eventType)}>
          {getEventIcon(eventType)}
          <span className="ml-1">{eventType}</span>
        </Badge>
      );
    },
  },
  {
    accessorKey: "ts",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Timestamp" />,
    cell: ({ row }) => (
      <div className="text-sm whitespace-nowrap">{formatDate(row.getValue("ts"))}</div>
    ),
  },
  {
    accessorKey: "seq",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Seq" />,
    cell: ({ row }) => (
      <div className="text-sm font-mono">{row.getValue("seq")}</div>
    ),
  },
  {
    accessorKey: "username",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Username" />,
    cell: ({ row }) => {
      const username = row.getValue("username") as string | null;
      return username ? (
        <div className="font-medium">{username}</div>
      ) : (
        <span className="text-xs text-muted-foreground">-</span>
      );
    },
  },
  {
    accessorKey: "ip_address",
    header: ({ column }) => <DataTableColumnHeader column={column} title="IP Address" />,
    cell: ({ row }) => {
      const ip = row.getValue("ip_address") as string | null;
      return ip ? (
        <div className="font-mono text-sm">{ip}</div>
      ) : (
        <span className="text-xs text-muted-foreground">-</span>
      );
    },
  },
  {
    accessorKey: "mac_address",
    header: ({ column }) => <DataTableColumnHeader column={column} title="MAC Address" />,
    cell: ({ row }) => {
      const mac = row.getValue("mac_address") as string | null;
      return mac ? (
        <div className="font-mono text-sm">{mac}</div>
      ) : (
        <span className="text-xs text-muted-foreground">-</span>
      );
    },
  },
  {
    accessorKey: "status",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Status" />,
    cell: ({ row }) => {
      const status = row.getValue("status") as string | null;
      return status ? (
        <Badge variant="secondary" className="text-xs">
          {status}
        </Badge>
      ) : (
        <span className="text-xs text-muted-foreground">-</span>
      );
    },
  },
  {
    accessorKey: "auth_state",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Auth State" />,
    cell: ({ row }) => {
      const authState = row.getValue("auth_state") as string | null;
      return authState ? (
        <Badge variant="outline" className="capitalize text-xs">
          {authState}
        </Badge>
      ) : (
        <span className="text-xs text-muted-foreground">-</span>
      );
    },
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
    accessorKey: "terminate_cause",
    header: ({ column }) => <DataTableColumnHeader column={column} title="Terminate Cause" />,
    cell: ({ row }) => {
      const cause = row.getValue("terminate_cause") as string | null;
      return cause && cause !== "" ? (
        <Badge variant="outline" className="text-xs">
          {cause}
        </Badge>
      ) : (
        <span className="text-xs text-muted-foreground">-</span>
      );
    },
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
];
