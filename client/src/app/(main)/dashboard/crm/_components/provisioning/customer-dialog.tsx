"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Customer } from "./types";

interface CustomerDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  customerEdit: Customer | null;
  customerForm: {
    name: string;
    email: string;
    phone: string;
    street: string;
    city: string;
    zip_code: string;
    state: string;
  };
  setCustomerForm: React.Dispatch<React.SetStateAction<{
    name: string;
    email: string;
    phone: string;
    street: string;
    city: string;
    zip_code: string;
    state: string;
  }>>;
  customerSaving: boolean;
  onSave: () => void;
}

export function CustomerDialog({
  open,
  onOpenChange,
  customerEdit,
  customerForm,
  setCustomerForm,
  customerSaving,
  onSave,
}: CustomerDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{customerEdit ? "Edit customer" : "Create customer"}</DialogTitle>
          <DialogDescription>Customers are OSS-side entities that can own multiple services.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor="customer-name">Name</Label>
            <Input
              id="customer-name"
              value={customerForm.name}
              onChange={(e) => setCustomerForm((s) => ({ ...s, name: e.target.value }))}
            />
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="customer-email">Email</Label>
              <Input
                id="customer-email"
                value={customerForm.email}
                onChange={(e) => setCustomerForm((s) => ({ ...s, email: e.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="customer-phone">Phone</Label>
              <Input
                id="customer-phone"
                value={customerForm.phone}
                onChange={(e) => setCustomerForm((s) => ({ ...s, phone: e.target.value }))}
              />
            </div>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="customer-street">Street</Label>
            <Input
              id="customer-street"
              value={customerForm.street}
              onChange={(e) => setCustomerForm((s) => ({ ...s, street: e.target.value }))}
            />
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="grid gap-2 sm:col-span-1">
              <Label htmlFor="customer-city">City</Label>
              <Input
                id="customer-city"
                value={customerForm.city}
                onChange={(e) => setCustomerForm((s) => ({ ...s, city: e.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="customer-state">State</Label>
              <Input
                id="customer-state"
                value={customerForm.state}
                onChange={(e) => setCustomerForm((s) => ({ ...s, state: e.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="customer-zip">ZIP</Label>
              <Input
                id="customer-zip"
                value={customerForm.zip_code}
                onChange={(e) => setCustomerForm((s) => ({ ...s, zip_code: e.target.value }))}
              />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={onSave} disabled={customerSaving}>
            {customerSaving ? "Saving..." : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
