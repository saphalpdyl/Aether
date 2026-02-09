import { z } from "zod";

export const routerSchema = z.object({
  router_name: z.string(),
  giaddr: z.string(),
  bng_id: z.string(),
  first_seen: z.string(),
  last_seen: z.string(),
  is_alive: z.string(),
  last_ping: z.string(),
  active_subscribers: z.preprocess((val) => Number(val), z.number()),
});

export type Router = z.infer<typeof routerSchema>;
