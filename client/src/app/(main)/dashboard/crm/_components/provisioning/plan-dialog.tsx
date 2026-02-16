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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { Plan } from "./types";

interface PlanDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  planEdit: Plan | null;
  planForm: {
    name: string;
    download_speed: string;
    upload_speed: string;
    download_burst: string;
    upload_burst: string;
    price: string;
    is_active: boolean;
  };
  setPlanForm: React.Dispatch<React.SetStateAction<{
    name: string;
    download_speed: string;
    upload_speed: string;
    download_burst: string;
    upload_burst: string;
    price: string;
    is_active: boolean;
  }>>;
  planSaving: boolean;
  onSave: () => void;
}

export function PlanDialog({
  open,
  onOpenChange,
  planEdit,
  planForm,
  setPlanForm,
  planSaving,
  onSave,
}: PlanDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{planEdit ? "Edit plan" : "Create plan"}</DialogTitle>
          <DialogDescription>Speed values are in kbps and burst values are in kbit.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor="plan-name">Name</Label>
            <Input id="plan-name" value={planForm.name} onChange={(e) => setPlanForm((s) => ({ ...s, name: e.target.value }))} />
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="plan-download">Download (kbps)</Label>
              <Input
                id="plan-download"
                type="number"
                min="1"
                value={planForm.download_speed}
                onChange={(e) => setPlanForm((s) => ({ ...s, download_speed: e.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="plan-upload">Upload (kbps)</Label>
              <Input
                id="plan-upload"
                type="number"
                min="1"
                value={planForm.upload_speed}
                onChange={(e) => setPlanForm((s) => ({ ...s, upload_speed: e.target.value }))}
              />
            </div>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="plan-download-burst">Download Burst (kbit)</Label>
              <Input
                id="plan-download-burst"
                type="number"
                min="1"
                value={planForm.download_burst}
                onChange={(e) => setPlanForm((s) => ({ ...s, download_burst: e.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="plan-upload-burst">Upload Burst (kbit)</Label>
              <Input
                id="plan-upload-burst"
                type="number"
                min="1"
                value={planForm.upload_burst}
                onChange={(e) => setPlanForm((s) => ({ ...s, upload_burst: e.target.value }))}
              />
            </div>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="plan-price">Price</Label>
              <Input
                id="plan-price"
                type="number"
                min="0"
                step="0.01"
                value={planForm.price}
                onChange={(e) => setPlanForm((s) => ({ ...s, price: e.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label>Status</Label>
              <Select
                value={planForm.is_active ? "true" : "false"}
                onValueChange={(value) => setPlanForm((s) => ({ ...s, is_active: value === "true" }))}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="true">Active</SelectItem>
                  <SelectItem value="false">Inactive</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={onSave} disabled={planSaving}>
            {planSaving ? "Saving..." : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
