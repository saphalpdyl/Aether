import { z } from "zod";

export const sessionEventSchema = z.object({
  bng_id: z.string(),
  bng_instance_id: z.string(),
  seq: z.preprocess((val) => (val === undefined || val === null ? 0 : Number(val)), z.number()),
  event_type: z.string(),
  ts: z.string(),
  session_id: z.string(),
  nas_ip: z.string(),
  circuit_id: z.string(),
  remote_id: z.string(),
  mac_address: z.string().nullable(),
  ip_address: z.string().nullable(),
  username: z.string().nullable(),
  // Coerce numeric fields
  input_octets: z.preprocess((val) => (val === undefined || val === null ? 0 : Number(val)), z.number()),
  output_octets: z.preprocess((val) => (val === undefined || val === null ? 0 : Number(val)), z.number()),
  input_packets: z.preprocess((val) => (val === undefined || val === null ? 0 : Number(val)), z.number()),
  output_packets: z.preprocess((val) => (val === undefined || val === null ? 0 : Number(val)), z.number()),
  status: z.string().nullable(),
  auth_state: z.string().nullable(),
  terminate_cause: z.string().nullable(),
});

export type SessionEvent = z.infer<typeof sessionEventSchema>;
