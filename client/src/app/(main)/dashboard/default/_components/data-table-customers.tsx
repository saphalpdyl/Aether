"use client";
"use no memo";

import * as React from "react";

import { flexRender } from "@tanstack/react-table";
import { ChevronDown, ChevronRight, Mail, MapPin, Phone } from "lucide-react";
import { DataTablePagination } from "@/components/data-table/data-table-pagination";
import { DataTableViewOptions } from "@/components/data-table/data-table-view-options";
import { useDataTableInstance } from "@/hooks/use-data-table-instance";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Download } from "lucide-react";
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
import { DisconnectButton } from "./disconnect-button";

interface DataTableCustomersProps {
  data: CustomerListing[];
  onRowClick?: (customer: CustomerListing) => void;
  expandedRow?: number | null;
}

interface ActiveSession {
  session_id: string;
  username: string;
  ip_address: string | null;
  mac_address: string | null;
  start_time: string;
  input_octets: string | null;
  output_octets: string | null;
}

interface Service {
  service_id: number;
  plan_name: string;
  circuit_id: string;
  remote_id: string;
  status: string;
}

function formatBytes(octets: string | null): string {
  if (!octets) return "—";
  const bytes = Number(octets);
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

function CustomerDetailRow({ customer }: { customer: CustomerListing }) {
  const [services, setServices] = React.useState<Service[]>([]);
  const [sessions, setSessions] = React.useState<ActiveSession[]>([]);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    const fetchDetails = async () => {
      setLoading(true);
      try {
        const [svcRes, sessRes] = await Promise.all([
          fetch(`/api/services?customer_id=${customer.id}`),
          fetch(`/api/customers/${customer.id}/sessions`),
        ]);
        if (svcRes.ok) {
          const svcData = await svcRes.json();
          setServices(svcData.data ?? []);
        }
        if (sessRes.ok) {
          const sessData = await sessRes.json();
          setSessions(sessData.data ?? []);
        }
      } catch (error) {
        console.error("Failed to fetch customer details:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchDetails();
  }, [customer.id]);

  if (loading) {
    return (
      <TableRow>
        <TableCell colSpan={customersColumns.length} className="bg-muted/30">
          <div className="p-4 text-center text-sm text-muted-foreground">Loading details...</div>
        </TableCell>
      </TableRow>
    );
  }

  return (
    <TableRow>
      <TableCell colSpan={customersColumns.length} className="bg-muted/30 p-0">
        <div className="p-6 space-y-6">
          {/* Contact Information */}
          <div className="space-y-2">
            <h4 className="text-sm font-semibold">Contact Information</h4>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="flex items-center gap-2">
                <Mail className="size-4 text-muted-foreground" />
                <span>{customer.email || "—"}</span>
              </div>
              <div className="flex items-center gap-2">
                <Phone className="size-4 text-muted-foreground" />
                <span>{customer.phone || "—"}</span>
              </div>
              <div className="flex items-center gap-2">
                <MapPin className="size-4 text-muted-foreground" />
                <span>
                  {[customer.street, customer.city, customer.state, customer.zip_code]
                    .filter(Boolean)
                    .join(", ") || "—"}
                </span>
              </div>
            </div>
          </div>

          {/* Services */}
          {services.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold">Services ({services.length})</h4>
              <div className="grid gap-2">
                {services.map((svc) => (
                  <div
                    key={svc.service_id}
                    className="flex items-center justify-between rounded-lg border bg-card p-3 text-sm"
                  >
                    <div className="space-y-1">
                      <div className="font-medium">{svc.plan_name}</div>
                      <div className="text-xs text-muted-foreground">
                        Circuit: {svc.circuit_id} | Remote: {svc.remote_id}
                      </div>
                    </div>
                    <Badge
                      variant={
                        svc.status === "ACTIVE"
                          ? "default"
                          : svc.status === "SUSPENDED"
                            ? "secondary"
                            : "destructive"
                      }
                    >
                      {svc.status}
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Active Sessions */}
          {sessions.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold">Active Sessions ({sessions.length})</h4>
              <div className="grid gap-2">
                {sessions.map((sess) => (
                  <div
                    key={sess.session_id}
                    className="rounded-lg border bg-card p-3 text-sm flex items-center gap-2"
                  >
                    <DisconnectButton variant="full" sessionId={sess.session_id} username={sess.username} />
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                      <div>
                        <span className="text-muted-foreground">IP:</span>{" "}
                        <span className="font-mono">{sess.ip_address ?? "—"}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">MAC:</span>{" "}
                        <span className="font-mono">{sess.mac_address ?? "—"}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Download:</span>{" "}
                        <span>{formatBytes(sess.input_octets)}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Upload:</span>{" "}
                        <span>{formatBytes(sess.output_octets)}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </TableCell>
    </TableRow>
  );
}

export function DataTableCustomers({ data: initialData, onRowClick, expandedRow }: DataTableCustomersProps) {
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
            <h3 className="text-base font-semibold">Customers</h3>
            <Badge variant="secondary" className="rounded-sm">{data.length}</Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            All customers and their online status
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="h-8">
            <Download className="size-4 mr-1" />
            Export (CSV)
          </Button>
          <DataTableViewOptions table={table} />
        </div>
      </div>
      <div className="overflow-hidden rounded-lg border bg-card">
        <Table>
          <TableHeader className="bg-muted/50">
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id} className="hover:bg-transparent">
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
                <React.Fragment key={row.id}>
                  <TableRow
                    data-state={row.getIsSelected() && "selected"}
                    className="cursor-pointer"
                    onClick={() => onRowClick?.(row.original)}
                  >
                    <TableCell className="w-8">
                      {expandedRow === row.original.id ? (
                        <ChevronDown className="size-4" />
                      ) : (
                        <ChevronRight className="size-4" />
                      )}
                    </TableCell>
                    {row.getVisibleCells().slice(1).map((cell) => (
                      <TableCell key={cell.id}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </TableCell>
                    ))}
                  </TableRow>
                  {expandedRow === row.original.id && <CustomerDetailRow customer={row.original} />}
                </React.Fragment>
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
