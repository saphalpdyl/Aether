import type { ColumnDef } from "@tanstack/react-table";
import { CircleCheck, XCircle, Server, MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import type { z } from "zod";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import { DataTableColumnHeader } from "../../../../../components/data-table/data-table-column-header";
import type { routerSchema } from "./routers-schema";

function formatDate(dateString: string | null): string {
  if (!dateString) return "—";
  return new Date(dateString).toLocaleString();
}

type RouterActionsProps = {
  onEdit?: (routerName: string) => void;
  onDelete?: (routerName: string) => void;
};

export function createRoutersColumns(actions?: RouterActionsProps): ColumnDef<z.infer<typeof routerSchema>>[] {
  return [
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
      accessorKey: "is_alive",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Status" />,
      cell: ({ row }) => {
        const isAlive = String(row.getValue("is_alive") ?? "").toLowerCase() === "true";
        return (
          <Badge variant={isAlive ? "default" : "secondary"}>
            {isAlive ? <CircleCheck className="mr-1 h-3 w-3" /> : <XCircle className="mr-1 h-3 w-3" />}
            {isAlive ? "Online" : "Offline"}
          </Badge>
        );
      },
    },
    {
      accessorKey: "router_name",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Router Name" />,
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
          <Server className="h-4 w-4 text-muted-foreground" />
          <span className="font-medium">{row.getValue("router_name")}</span>
        </div>
      ),
    },
    {
      accessorKey: "bng_id",
      header: ({ column }) => <DataTableColumnHeader column={column} title="BNG ID" />,
      cell: ({ row }) => <div className="text-sm">{row.getValue("bng_id") ?? "—"}</div>,
    },
    {
      accessorKey: "giaddr",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Gateway IP" />,
      cell: ({ row }) => <div className="font-mono text-sm">{row.getValue("giaddr")}</div>,
    },
    {
      accessorKey: "active_subscribers",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Active Subscribers" />,
      cell: ({ row }) => (
        <div className="text-sm font-semibold">
          {Number(row.getValue("active_subscribers") ?? 0).toLocaleString()}
        </div>
      ),
    },
    {
      accessorKey: "created_at",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Created At" />,
      cell: ({ row }) => (
        <div className="text-sm whitespace-nowrap">{formatDate(row.getValue("created_at"))}</div>
      ),
    },
    {
      accessorKey: "last_seen",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Last Seen" />,
      cell: ({ row }) => (
        <div className="text-sm whitespace-nowrap">{formatDate(row.getValue("last_seen"))}</div>
      ),
    },
    {
      accessorKey: "last_ping",
      header: ({ column }) => <DataTableColumnHeader column={column} title="Last Ping" />,
      cell: ({ row }) => (
        <div className="text-sm whitespace-nowrap">{formatDate(row.getValue("last_ping"))}</div>
      ),
    },
    {
      id: "actions",
      cell: ({ row }) => {
        const routerName = row.getValue("router_name") as string;
        return (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <MoreHorizontal className="h-4 w-4" />
                <span className="sr-only">Open menu</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => actions?.onEdit?.(routerName)}>
                <Pencil className="mr-2 h-4 w-4" />
                Edit
              </DropdownMenuItem>
              <DropdownMenuItem
                variant="destructive"
                onClick={() => actions?.onDelete?.(routerName)}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        );
      },
      enableSorting: false,
      enableHiding: false,
    },
  ];
}

// Default export for backwards compatibility
export const routersColumns = createRoutersColumns();
