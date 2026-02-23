"use client";

import { useCallback, useEffect, useState } from "react";
import { Mail, Phone, MapPin } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

import { DisconnectButton } from "./disconnect-button";
import type { CustomerListing } from "./customers-schema";

interface Service {
  id: number;
  plan_name: string;
  circuit_id: string;
  remote_id: string;
  status: string;
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

function formatDate(dateString: string | null): string {
  if (!dateString) return "\u2014";
  return new Date(dateString).toLocaleString();
}

function formatBytes(octets: string | null): string {
  if (!octets) return "\u2014";
  const bytes = Number(octets);
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

const serviceStatusVariant: Record<string, "default" | "secondary" | "destructive"> = {
  ACTIVE: "default",
  SUSPENDED: "secondary",
  TERMINATED: "destructive",
};

interface CustomerDetailSheetProps {
  customer: CustomerListing | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CustomerDetailSheet({ customer, open, onOpenChange }: CustomerDetailSheetProps) {
  const [services, setServices] = useState<Service[]>([]);
  const [sessions, setSessions] = useState<ActiveSession[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchDetails = useCallback(async (customerId: number) => {
    setLoading(true);
    try {
      const [svcRes, sessRes] = await Promise.all([
        fetch(`/api/services?customer_id=${customerId}`),
        fetch(`/api/customers/${customerId}/sessions`),
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
  }, []);

  useEffect(() => {
    if (customer && open) {
      fetchDetails(customer.id);
    } else {
      setServices([]);
      setSessions([]);
    }
  }, [customer, open, fetchDetails]);

  const address = customer
    ? [customer.street, customer.city, customer.state, customer.zip_code].filter(Boolean).join(", ")
    : null;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-lg overflow-y-auto">
        {customer && (
          <>
            <SheetHeader>
              <SheetTitle>{customer.name}</SheetTitle>
              <SheetDescription>Customer details, services, and active sessions</SheetDescription>
            </SheetHeader>

            <div className="flex flex-col gap-4 px-4 pb-4">
              {/* Contact info */}
              <div className="flex flex-col gap-2 text-sm">
                {customer.email && (
                  <div className="flex items-center gap-2">
                    <Mail className="h-4 w-4 text-muted-foreground" />
                    {customer.email}
                  </div>
                )}
                {customer.phone && (
                  <div className="flex items-center gap-2">
                    <Phone className="h-4 w-4 text-muted-foreground" />
                    {customer.phone}
                  </div>
                )}
                {address && (
                  <div className="flex items-center gap-2">
                    <MapPin className="h-4 w-4 text-muted-foreground" />
                    {address}
                  </div>
                )}
              </div>

              <Separator />

              {/* Services */}
              <div>
                <h4 className="text-sm font-semibold mb-2">
                  Services{" "}
                  <Badge variant="secondary" className="ml-1">{services.length}</Badge>
                </h4>
                {loading ? (
                  <p className="text-sm text-muted-foreground">Loading...</p>
                ) : services.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No services</p>
                ) : (
                  <div className="flex flex-col gap-2">
                    {services.map((svc) => (
                      <div
                        key={svc.id}
                        className="rounded-md border p-3 text-sm flex flex-col gap-1"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-medium">{svc.plan_name}</span>
                          <Badge variant={serviceStatusVariant[svc.status] ?? "secondary"}>
                            {svc.status}
                          </Badge>
                        </div>
                        <div className="text-muted-foreground text-xs font-mono">
                          Circuit: {svc.circuit_id} | Remote: {svc.remote_id}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <Separator />

              {/* Active sessions */}
              <div>
                <h4 className="text-sm font-semibold mb-2">
                  Active Sessions{" "}
                  <Badge variant="secondary" className="ml-1">{sessions.length}</Badge>
                </h4>
                {loading ? (
                  <p className="text-sm text-muted-foreground">Loading...</p>
                ) : sessions.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No active sessions</p>
                ) : (
                  <div className="flex flex-col gap-2">
                    {sessions.map((sess) => (
                      <div
                        key={sess.session_id}
                        className="rounded-md border p-3 text-sm flex flex-col gap-2"
                      >
                        <div className="font-mono text-xs truncate">
                          {sess.session_id}
                        </div>
                        <div className="flex gap-4 text-muted-foreground text-xs">
                          <span>IP: {sess.ip_address ?? "\u2014"}</span>
                          <span>MAC: {sess.mac_address ?? "\u2014"}</span>
                        </div>
                        <div className="flex gap-4 text-muted-foreground text-xs">
                          <span>Started: {formatDate(sess.start_time)}</span>
                        </div>
                        <div className="flex gap-4 text-muted-foreground text-xs">
                          <span>In: {formatBytes(sess.input_octets)}</span>
                          <span>Out: {formatBytes(sess.output_octets)}</span>
                        </div>
                        <DisconnectButton sessionId={sess.session_id} username={sess.username} />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
