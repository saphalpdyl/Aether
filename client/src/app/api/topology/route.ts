import { NextResponse } from "next/server";
import { BACKEND_URL } from "@/config/backend";


export const dynamic = "force-dynamic";

interface ClabNode {
  kind?: string;
  image?: string;
  [key: string]: unknown;
}

interface ClabTopology {
  name?: string;
  topology: {
    nodes: Record<string, ClabNode>;
    links: Array<{ endpoints: [string, string] }>;
  };
}

export interface TopoNode {
  id: string;
  label: string;
  group: "bng" | "agg" | "relay" | "host" | "wan" | "service";
  image?: string;
  kind?: string;
}

export interface TopoLink {
  id: number;
  from: string;
  to: string;
  fromPort: string;
  toPort: string;
}

export interface TopologyData {
  name: string;
  nodes: TopoNode[];
  links: TopoLink[];
}

function getGroup(name: string): TopoNode["group"] {
  if (/^bng-\d/.test(name)) return "bng";
  if (/^agg-/.test(name)) return "agg";
  if (/^h-/.test(name)) return "host";
  if (/relay/i.test(name)) return "relay";
  if (name === "wan" || name === "upstream" || name.includes("macvlan")) return "wan";
  return "service";
}

export async function GET() {
  const topologyUrl = `${BACKEND_URL}/api/simulation/topology`;

  try {
    const response = await fetch(topologyUrl, {
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch topology: ${response.statusText}`);
    }

    const topo = (await response.json()) as ClabTopology;

    const nodes: TopoNode[] = Object.entries(topo.topology.nodes).map(([name, cfg]) => ({
      id: name,
      label: name,
      group: getGroup(name),
      image: cfg.image,
      kind: cfg.kind,
    }));

    const links: TopoLink[] = topo.topology.links.map((link, i) => {
      const [fromEp, toEp] = link.endpoints;
      const colonFrom = fromEp.lastIndexOf(":");
      const colonTo = toEp.lastIndexOf(":");
      const from = fromEp.slice(0, colonFrom);
      const fromPort = fromEp.slice(colonFrom + 1);
      const to = toEp.slice(0, colonTo);
      const toPort = toEp.slice(colonTo + 1);
      return { id: i, from, to, fromPort, toPort };
    });

    const data: TopologyData = { name: topo.name ?? "topology", nodes, links };
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}

