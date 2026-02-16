import { z } from "zod";

export const customerListingSchema = z.object({
  id: z.preprocess(Number, z.number()),
  name: z.string(),
  email: z.string().nullable(),
  phone: z.string().nullable(),
  street: z.string().nullable(),
  city: z.string().nullable(),
  zip_code: z.string().nullable(),
  state: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
  active_sessions: z.preprocess(Number, z.number()),
  recent_sessions: z.preprocess(Number, z.number()),
  service_count: z.preprocess(Number, z.number()),
  status: z.enum(["online", "recent", "new", "offline"]),
  ip_assignments: z.string().nullable().optional(),
});

export type CustomerListing = z.infer<typeof customerListingSchema>;
