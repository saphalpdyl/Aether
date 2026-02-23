"use client";

import { Pencil, Plus, Search, Trash2 } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Customer, DeleteTarget } from "./types";

interface CustomerTabProps {
  customers: Customer[];
  loading: boolean;
  customerQuery: string;
  setCustomerQuery: (query: string) => void;
  filteredCustomers: Customer[];
  onCreateCustomer: () => void;
  onEditCustomer: (customer: Customer) => void;
  onDeleteCustomer: (target: DeleteTarget) => void;
}

export function CustomerTab({
  customers,
  loading,
  customerQuery,
  setCustomerQuery,
  filteredCustomers,
  onCreateCustomer,
  onEditCustomer,
  onDeleteCustomer,
}: CustomerTabProps) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative w-full sm:max-w-sm">
            <Search className="text-muted-foreground absolute top-2.5 left-2.5 h-4 w-4" />
            <Input
              placeholder="Search customers"
              value={customerQuery}
              onChange={(e) => setCustomerQuery(e.target.value)}
              className="pl-8"
            />
          </div>
          <Button onClick={onCreateCustomer}>
            <Plus className="mr-1 h-4 w-4" />
            New Customer
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Phone</TableHead>
              <TableHead>Location</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={5} className="text-muted-foreground py-6 text-center">
                  Loading customers...
                </TableCell>
              </TableRow>
            ) : filteredCustomers.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-muted-foreground py-6 text-center">
                  No customers found
                </TableCell>
              </TableRow>
            ) : (
              filteredCustomers.map((customer) => (
                <TableRow key={customer.id}>
                  <TableCell className="font-medium">
                    <Link 
                      href={`/dashboard/crm/customers/${customer.id}`}
                      className="text-blue-600 dark:text-blue-400 hover:underline"
                    >
                      {customer.name}
                    </Link>
                  </TableCell>
                  <TableCell>{customer.email || "-"}</TableCell>
                  <TableCell>{customer.phone || "-"}</TableCell>
                  <TableCell>{[customer.city, customer.state].filter(Boolean).join(", ") || "-"}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button variant="outline" size="sm" onClick={() => onEditCustomer(customer)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          onDeleteCustomer({ type: "customer", id: customer.id, label: customer.name })
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
