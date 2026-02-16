"use client";

import { useCallback, useEffect, useState } from "react";

import { customerListingSchema } from "./customers-schema";
import type { CustomerListing } from "./customers-schema";
import { DataTableCustomers } from "./data-table-customers";

export default function CustomersTable() {
  const [customers, setCustomers] = useState<CustomerListing[]>([]);
  const [expandedRow, setExpandedRow] = useState<number | null>(null);

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
        
        // Fetch IP assignments for customers with active sessions
        const customersWithIPs = await Promise.all(
          validated.map(async (customer: CustomerListing) => {
            if (customer.active_sessions > 0) {
              try {
                const sessionsRes = await fetch(`/api/customers/${customer.id}/sessions`);
                if (sessionsRes.ok) {
                  const sessionsData = await sessionsRes.json();
                  const sessions = sessionsData.data ?? [];
                  const ips = sessions
                    .map((s: { ip_address: string | null }) => s.ip_address)
                    .filter((ip: string | null): ip is string => ip !== null);
                  return {
                    ...customer,
                    ip_assignments: ips.length > 0 ? ips.join(", ") : null,
                  };
                }
              } catch {
                // If fetching sessions fails, return customer without IP assignments
              }
            }
            return customer;
          })
        );
        
        setCustomers(customersWithIPs);
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
    setExpandedRow(expandedRow === customer.id ? null : customer.id);
  }, [expandedRow]);

  return (
    <DataTableCustomers 
      data={customers} 
      onRowClick={handleRowClick}
      expandedRow={expandedRow}
    />
  );
}
