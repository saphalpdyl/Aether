import { z } from "zod";

export const routerSchema = z.object({
  router_name: z.string(),
  giaddr: z.string(),
  bng_id: z.string().nullable(),
  is_alive: z.string(),
  last_seen: z.string().nullable(),
  last_ping: z.string().nullable(),
  active_subscribers: z.preprocess((val) => Number(val), z.number()),
  created_at: z.string(),
  updated_at: z.string(),
});

export type Router = z.infer<typeof routerSchema>;
