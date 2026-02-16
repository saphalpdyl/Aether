"use client";

import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";

const createRouterSchema = z.object({
  router_name: z.string().min(1, "Router name is required"),
  giaddr: z.string().min(1, "Gateway IP is required"),
  bng_id: z.string().optional(),
  total_interfaces: z.coerce.number().int().min(2, "Minimum 2 interfaces"),
});

type CreateRouterValues = z.infer<typeof createRouterSchema>;

interface RouterCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated?: () => void;
}

export function RouterCreateDialog({ open, onOpenChange, onCreated }: RouterCreateDialogProps) {
  const [loading, setLoading] = useState(false);

  const form = useForm<CreateRouterValues>({
    resolver: zodResolver(createRouterSchema),
    defaultValues: {
      router_name: "",
      giaddr: "",
      bng_id: "",
      total_interfaces: 5,
    },
  });

  const onSubmit = async (data: CreateRouterValues) => {
    setLoading(true);
    try {
      const response = await fetch("/api/routers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          router_name: data.router_name,
          giaddr: data.giaddr,
          bng_id: data.bng_id || null,
          total_interfaces: data.total_interfaces,
        }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.error || `Failed to create router (${response.status})`);
      }

      toast.success(`Router "${data.router_name}" created`);
      form.reset();
      onOpenChange(false);
      onCreated?.();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to create router");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New Access Node</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="router_name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Router Name</FormLabel>
                  <FormControl>
                    <Input placeholder="e.g. OLT-RACK1-01" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="giaddr"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Gateway IP (giaddr)</FormLabel>
                  <FormControl>
                    <Input placeholder="e.g. 10.0.0.1" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="total_interfaces"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Total Interfaces</FormLabel>
                  <FormControl>
                    <Input type="number" min="2" placeholder="e.g. 5" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="bng_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>BNG ID (optional)</FormLabel>
                  <FormControl>
                    <Input placeholder="e.g. bng-01" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={loading}>
                {loading ? "Creating..." : "Create"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
