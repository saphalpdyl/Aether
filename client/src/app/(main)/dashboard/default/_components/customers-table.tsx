"use client";

import { useCallback, useEffect, useState } from "react";

import { customerListingSchema } from "./customers-schema";
import type { CustomerListing } from "./customers-schema";
import { DataTableCustomers } from "./data-table-customers";
import { CustomerDetailSheet } from "./customer-detail-sheet";

export default function CustomersTable() {
  const [customers, setCustomers] = useState<CustomerListing[]>([]);
  const [selected, setSelected] = useState<CustomerListing | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const response = await fetch("/api/customers/listing");
      if (response.ok) {
        const result = await response.json();
        const validated = (result.data ?? [])
          .map((row: unknown) => {
            try {
              return customerListingSchema.parse(row);
            } catch {
              return null;
            }
          })
          .filter((c: CustomerListing | null): c is CustomerListing => c !== null);
        setCustomers(validated);
      }
    } catch (error) {
      console.error("Failed to fetch customers:", error);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleRowClick = useCallback((customer: CustomerListing) => {
    setSelected(customer);
    setSheetOpen(true);
  }, []);

  return (
    <>
      <DataTableCustomers data={customers} onRowClick={handleRowClick} />
      <CustomerDetailSheet
        customer={selected}
        open={sheetOpen}
        onOpenChange={setSheetOpen}
      />
    </>
  );
}
