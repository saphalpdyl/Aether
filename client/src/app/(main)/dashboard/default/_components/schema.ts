import { z } from "zod";

export const sessionSchema = z.object({
  session_id: z.string(),
  bng_id: z.string(),
  bng_instance_id: z.string(),
  nas_ip: z.string(),
  circuit_id: z.string(),
  remote_id: z.string(),
  mac_address: z.string(),
  ip_address: z.string(),
  username: z.string(),
  start_time: z.string(),
  last_update: z.string(),
  // API returns octets/packets as strings; coerce to numbers
  input_octets: z.preprocess((val) => (val === undefined || val === null ? 0 : Number(val)), z.number()),
  output_octets: z.preprocess((val) => (val === undefined || val === null ? 0 : Number(val)), z.number()),
  input_packets: z.preprocess((val) => (val === undefined || val === null ? 0 : Number(val)), z.number()),
  output_packets: z.preprocess((val) => (val === undefined || val === null ? 0 : Number(val)), z.number()),
  status: z.string(),
  auth_state: z.string(),
});

export type Session = z.infer<typeof sessionSchema>;
