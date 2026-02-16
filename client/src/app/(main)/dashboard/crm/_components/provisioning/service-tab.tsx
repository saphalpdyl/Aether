"use client";

import { Pencil, Plus, Search, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Service, DeleteTarget } from "./types";
import { statusBadgeVariant } from "./constants";

interface ServiceTabProps {
  services: Service[];
  loading: boolean;
  serviceQuery: string;
  setServiceQuery: (query: string) => void;
  serviceStatusFilter: "ALL" | Service["status"];
  setServiceStatusFilter: (filter: "ALL" | Service["status"]) => void;
  filteredServices: Service[];
  plansCount: number;
  customersCount: number;
  onCreateService: () => void;
  onEditService: (service: Service) => void;
  onDeleteService: (target: DeleteTarget) => void;
}

export function ServiceTab({
  services,
  loading,
  serviceQuery,
  setServiceQuery,
  serviceStatusFilter,
  setServiceStatusFilter,
  filteredServices,
  plansCount,
  customersCount,
  onCreateService,
  onEditService,
  onDeleteService,
}: ServiceTabProps) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="relative w-full sm:max-w-sm">
              <Search className="text-muted-foreground absolute top-2.5 left-2.5 h-4 w-4" />
              <Input
                placeholder="Search services"
                value={serviceQuery}
                onChange={(e) => setServiceQuery(e.target.value)}
                className="pl-8"
              />
            </div>
            <Button onClick={onCreateService} disabled={plansCount === 0 || customersCount === 0}>
              <Plus className="mr-1 h-4 w-4" />
              New Service
            </Button>
          </div>
          <div className="w-full sm:max-w-55">
            <Select
              value={serviceStatusFilter}
              onValueChange={(value: "ALL" | Service["status"]) => setServiceStatusFilter(value)}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Filter by status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">All statuses</SelectItem>
                <SelectItem value="ACTIVE">Active</SelectItem>
                <SelectItem value="SUSPENDED">Suspended</SelectItem>
                <SelectItem value="TERMINATED">Terminated</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {plansCount === 0 || customersCount === 0 ? (
          <p className="text-muted-foreground rounded-lg border border-dashed p-4 text-sm">
            Create at least one plan and one customer before creating services.
          </p>
        ) : null}
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Customer</TableHead>
              <TableHead>Plan</TableHead>
              <TableHead>Circuit ID</TableHead>
              <TableHead>Remote ID</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={6} className="text-muted-foreground py-6 text-center">
                  Loading services...
                </TableCell>
              </TableRow>
            ) : filteredServices.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-muted-foreground py-6 text-center">
                  No services found
                </TableCell>
              </TableRow>
            ) : (
              filteredServices.map((service) => (
                <TableRow key={service.id}>
                  <TableCell className="font-medium">{service.customer_name}</TableCell>
                  <TableCell>{service.plan_name}</TableCell>
                  <TableCell>{service.circuit_id}</TableCell>
                  <TableCell>{service.remote_id}</TableCell>
                  <TableCell>
                    <Badge variant={statusBadgeVariant[service.status]}>{service.status}</Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button variant="outline" size="sm" onClick={() => onEditService(service)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          onDeleteService({
                            type: "service",
                            id: service.id,
                            label: `${service.customer_name} • ${service.circuit_id}`,
                          })
                        }
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
