/**
 * Plan management tab component
 */

import { useMemo, useState } from "react";
import { Pencil, Plus, Search, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
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
import type { DeleteTarget, Plan } from "./provisioning-types";

interface PlanTabProps {
  plans: Plan[];
  loading: boolean;
  onCreatePlan: () => void;
  onEditPlan: (plan: Plan) => void;
  onDeletePlan: (target: DeleteTarget) => void;
}

export function PlanTab({ plans, loading, onCreatePlan, onEditPlan, onDeletePlan }: PlanTabProps) {
  const [planQuery, setPlanQuery] = useState("");

  const filteredPlans = useMemo(() => {
    const q = planQuery.trim().toLowerCase();
    if (!q) return plans;
    return plans.filter((p) => p.name.toLowerCase().includes(q));
  }, [plans, planQuery]);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative w-full sm:max-w-sm">
            <Search className="text-muted-foreground absolute top-2.5 left-2.5 h-4 w-4" />
            <Input
              placeholder="Search plans"
              value={planQuery}
              onChange={(e) => setPlanQuery(e.target.value)}
              className="pl-8"
            />
          </div>
          <Button onClick={onCreatePlan}>
            <Plus className="mr-1 h-4 w-4" />
            New Plan
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Download</TableHead>
              <TableHead>Upload</TableHead>
              <TableHead>Download Burst</TableHead>
              <TableHead>Upload Burst</TableHead>
              <TableHead>Price</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={8} className="text-muted-foreground py-6 text-center">
                  Loading plans...
                </TableCell>
              </TableRow>
            ) : filteredPlans.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="text-muted-foreground py-6 text-center">
                  No plans found
                </TableCell>
              </TableRow>
            ) : (
              filteredPlans.map((plan) => (
                <TableRow key={plan.id}>
                  <TableCell className="font-medium">{plan.name}</TableCell>
                  <TableCell>{plan.download_speed} kbps</TableCell>
                  <TableCell>{plan.upload_speed} kbps</TableCell>
                  <TableCell>{plan.download_burst} kbit</TableCell>
                  <TableCell>{plan.upload_burst} kbit</TableCell>
                  <TableCell>${Number(plan.price).toFixed(2)}</TableCell>
                  <TableCell>
                    <Badge variant={plan.is_active ? "default" : "secondary"}>
                      {plan.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button variant="outline" size="sm" onClick={() => onEditPlan(plan)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => onDeletePlan({ type: "plan", id: plan.id, label: plan.name })}
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
