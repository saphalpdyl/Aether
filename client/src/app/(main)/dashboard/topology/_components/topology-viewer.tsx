"use client";

import { useEffect, useRef, useState } from "react";

import type { TopoLink, TopologyData, TopoNode } from "@/app/api/topology/route";
import { usePreferencesStore } from "@/stores/preferences/preferences-provider";

// ── SVG icon helpers ────────────────────────────────────────────────────────

function svgURI(body: string): string {
  const s = `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 40 40'>${body}</svg>`;
  return "data:image/svg+xml;charset=utf-8," + encodeURIComponent(s);
}

const IMG_BNG = svgURI(`
  <rect width='40' height='40' rx='6' fill='#e6faf4' stroke='#00966a' stroke-width='1.5'/>
  <rect x='7' y='13' width='26' height='14' rx='3' fill='none' stroke='#00966a' stroke-width='1.5'/>
  <circle cx='13' cy='20' r='2.5' fill='#00966a'/>
  <circle cx='20' cy='20' r='2.5' fill='#00966a66'/>
  <circle cx='27' cy='20' r='2.5' fill='#00966a'/>
  <line x1='20' y1='7' x2='20' y2='13' stroke='#00966a' stroke-width='1.5'/>
  <line x1='20' y1='27' x2='20' y2='33' stroke='#00966a' stroke-width='1.5'/>
  <polyline points='16,10 20,6 24,10' fill='none' stroke='#00966a' stroke-width='1.5' stroke-linejoin='round'/>
  <polyline points='16,30 20,34 24,30' fill='none' stroke='#00966a' stroke-width='1.5' stroke-linejoin='round'/>
`);

const IMG_AGG = svgURI(`
  <rect width='40' height='40' rx='6' fill='#eaf1ff' stroke='#1a6fd4' stroke-width='1.5'/>
  <rect x='6' y='9'  width='28' height='7' rx='2' fill='none' stroke='#1a6fd4' stroke-width='1.5'/>
  <rect x='6' y='19' width='28' height='7' rx='2' fill='none' stroke='#1a6fd4' stroke-width='1.5'/>
  <rect x='6' y='29' width='28' height='5' rx='2' fill='none' stroke='#1a6fd444' stroke-width='1'/>
  <line x1='13' y1='16' x2='13' y2='19' stroke='#1a6fd4' stroke-width='1.2'/>
  <line x1='20' y1='16' x2='20' y2='19' stroke='#1a6fd4' stroke-width='1.2'/>
  <line x1='27' y1='16' x2='27' y2='19' stroke='#1a6fd4' stroke-width='1.2'/>
  <circle cx='10' cy='12.5' r='1.5' fill='#1a6fd4'/>
  <circle cx='16' cy='12.5' r='1.5' fill='#00966a'/>
  <circle cx='10' cy='22.5' r='1.5' fill='#1a6fd4'/>
  <circle cx='16' cy='22.5' r='1.5' fill='#d4600a'/>
`);

const IMG_RELAY = svgURI(`
  <rect width='40' height='40' rx='6' fill='#e6f8fc' stroke='#0891b2' stroke-width='1.5'/>
  <rect x='6' y='18' width='28' height='9' rx='2' fill='none' stroke='#0891b2' stroke-width='1.5'/>
  <line x1='11' y1='18' x2='11' y2='10' stroke='#0891b2' stroke-width='1.2'/>
  <line x1='17' y1='18' x2='17' y2='8'  stroke='#0891b2' stroke-width='1.2'/>
  <line x1='23' y1='18' x2='23' y2='8'  stroke='#0891b2' stroke-width='1.2'/>
  <line x1='29' y1='18' x2='29' y2='10' stroke='#0891b2' stroke-width='1.2'/>
  <circle cx='11' cy='9'  r='1.5' fill='#0891b2'/>
  <circle cx='17' cy='7'  r='1.5' fill='#0891b2'/>
  <circle cx='23' cy='7'  r='1.5' fill='#0891b2'/>
  <circle cx='29' cy='9'  r='1.5' fill='#0891b2'/>
  <line x1='11' y1='27' x2='11' y2='33' stroke='#0891b266' stroke-width='1'/>
  <line x1='20' y1='27' x2='20' y2='35' stroke='#0891b266' stroke-width='1'/>
  <line x1='29' y1='27' x2='29' y2='33' stroke='#0891b266' stroke-width='1'/>
`);

const IMG_HOST = svgURI(`
  <rect width='40' height='40' rx='6' fill='#f0f4f8' stroke='#8aaac8' stroke-width='1.2'/>
  <rect x='8'  y='9'  width='24' height='16' rx='2' fill='none' stroke='#6a8aa8' stroke-width='1.5'/>
  <rect x='11' y='12' width='18' height='10' rx='1' fill='#dce8f4'/>
  <line x1='20' y1='25' x2='20' y2='29' stroke='#6a8aa8' stroke-width='1.5'/>
  <line x1='13' y1='29' x2='27' y2='29' stroke='#6a8aa8' stroke-width='1.5'/>
  <line x1='8'  y1='34' x2='32' y2='34' stroke='#6a8aa833' stroke-width='1'/>
  <polyline points='13,19 16,15 19,18 22,14 27,19' fill='none' stroke='#6a8aa8' stroke-width='1' stroke-linejoin='round'/>
`);

const IMG_WAN = svgURI(`
  <rect width='40' height='40' rx='6' fill='#fff4ec' stroke='#d4600a' stroke-width='1.5'/>
  <circle cx='20' cy='20' r='12' fill='none' stroke='#d4600a' stroke-width='1.5'/>
  <ellipse cx='20' cy='20' rx='6'  ry='12' fill='none' stroke='#d4600a' stroke-width='1'/>
  <line x1='8' y1='20' x2='32' y2='20' stroke='#d4600a' stroke-width='1'/>
  <line x1='10' y1='14' x2='30' y2='14' stroke='#d4600a' stroke-width='0.8'/>
  <line x1='10' y1='26' x2='30' y2='26' stroke='#d4600a' stroke-width='0.8'/>
`);

const IMG_UPSTREAM = svgURI(`
  <rect width='40' height='40' rx='6' fill='#fff4ec' stroke='#d4600a' stroke-width='1.5'/>
  <line x1='20' y1='30' x2='20' y2='12' stroke='#d4600a' stroke-width='2' stroke-linecap='round'/>
  <polyline points='13,18 20,10 27,18' fill='none' stroke='#d4600a' stroke-width='2' stroke-linejoin='round'/>
  <line x1='10' y1='34' x2='30' y2='34' stroke='#d4600a' stroke-width='1.5' stroke-linecap='round'/>
`);

const IMG_MACVLAN = svgURI(`
  <rect width='40' height='40' rx='6' fill='#fff4ec' stroke='#d4600a88' stroke-width='1.2'/>
  <rect x='8' y='14' width='24' height='12' rx='2' fill='none' stroke='#d4600a' stroke-width='1.2'/>
  <text x='20' y='23' font-family='monospace' font-size='8' fill='#d4600a' text-anchor='middle'>MACVLAN</text>
`);

const IMG_SERVICE = svgURI(`
  <rect width='40' height='40' rx='6' fill='#f5f0ff' stroke='#7c3aed' stroke-width='1.5'/>
  <rect x='7' y='7'  width='26' height='7' rx='1.5' fill='none' stroke='#7c3aed' stroke-width='1.5'/>
  <rect x='7' y='17' width='26' height='7' rx='1.5' fill='none' stroke='#7c3aed' stroke-width='1.5'/>
  <rect x='7' y='27' width='26' height='7' rx='1.5' fill='none' stroke='#7c3aed55' stroke-width='1'/>
  <circle cx='28' cy='10.5' r='2' fill='#7c3aed'/>
  <circle cx='23' cy='10.5' r='2' fill='#00966a'/>
  <circle cx='28' cy='20.5' r='2' fill='#7c3aed'/>
  <circle cx='23' cy='20.5' r='2' fill='#d4600a'/>
  <rect x='10' y='29.5' width='12' height='2' rx='1' fill='#7c3aed33'/>
`);

const IMG_MGMT = svgURI(`
  <rect width='40' height='40' rx='6' fill='#f5f0ff' stroke='#7c3aed' stroke-width='1.5'/>
  <circle cx='20' cy='20' r='6'  fill='none' stroke='#7c3aed' stroke-width='2'/>
  <circle cx='20' cy='20' r='10' fill='none' stroke='#7c3aed44' stroke-width='1' stroke-dasharray='3 2'/>
  <line x1='20' y1='8'  x2='20' y2='14' stroke='#7c3aed' stroke-width='1.5'/>
  <line x1='20' y1='26' x2='20' y2='32' stroke='#7c3aed' stroke-width='1.5'/>
  <line x1='8'  y1='20' x2='14' y2='20' stroke='#7c3aed' stroke-width='1.5'/>
  <line x1='26' y1='20' x2='32' y2='20' stroke='#7c3aed' stroke-width='1.5'/>
  <circle cx='20' cy='20' r='3' fill='#7c3aed'/>
`);

type Point = {
  x: number;
  y: number;
}

// ── Icon + font color maps ───────────────────────────────────────────────────

function getNodeImage(id: string, group: string): string {
  if (id === "mgmt") return IMG_MGMT;
  if (id === "upstream") return IMG_UPSTREAM;
  if (id.includes("macvlan")) return IMG_MACVLAN;
  switch (group) {
    case "bng":
      return IMG_BNG;
    case "agg":
      return IMG_AGG;
    case "relay":
      return IMG_RELAY;
    case "host":
      return IMG_HOST;
    case "wan":
      return IMG_WAN;
    default:
      return IMG_SERVICE;
  }
}

function getNodeSize(group: string): number {
  switch (group) {
    case "bng":
      return 30;
    case "agg":
      return 26;
    case "relay":
      return 22;
    case "wan":
      return 22;
    default:
      return 16;
  }
}

const FONT_COLORS_LIGHT: Record<string, string> = {
  bng: "#00966a",
  agg: "#1a6fd4",
  relay: "#0891b2",
  service: "#7c3aed",
  wan: "#d4600a",
  host: "#4a6a8a",
};

const FONT_COLORS_DARK: Record<string, string> = {
  bng: "#2acc8a",
  agg: "#4a8fe4",
  relay: "#18b1d2",
  service: "#9c6aff",
  wan: "#e47030",
  host: "#8aaac8",
};

// ── Edge color constants ────────────────────────────────────────────────────

const DATA = "#4aaa80";
const MGMT = "#9b6ee0";
const WAN = "#e08040";
const HOST = "#90b8d8";
const AGG = "#5090d8";

function getEdgeColor(from: string, to: string, isDark: boolean): { color: string; width: number; dashed: boolean } {
  const bothWan = [from, to].some((n) => ["wan", "upstream", "macvlan"].includes(n) || n.includes("macvlan"));
  const anyHost = [from, to].some((n) => n.startsWith("h-"));
  const anyBng = [from, to].some((n) => n.startsWith("bng-"));
  const anyMgmt = [from, to].some(
    (n) =>
      n === "mgmt" ||
      n === "upstream" ||
      n === "kea" ||
      n === "radius" ||
      n === "radius_pg" ||
      n === "dhcp_pg" ||
      n === "redis" ||
      n === "oss_pg" ||
      n === "bng_ingestor" ||
      n === "frontend" ||
      n === "backend" ||
      n === "simulator" ||
      n === "nginx",
  );
  const anyAgg = [from, to].some((n) => n.startsWith("agg-"));
  const bothCore = anyBng && anyAgg;

  if (anyHost) return { color: HOST, width: 1.2, dashed: false };
  if (bothCore) return { color: DATA, width: 4.5, dashed: false };
  if (anyAgg && !anyBng) return { color: AGG, width: 3, dashed: false };
  if (bothWan || (anyBng && [from, to].some((n) => n === "wan"))) return { color: WAN, width: 3.5, dashed: false };
  if (anyMgmt && !anyHost) return { color: "#fff0", width: anyBng ? 2 : 1.5, dashed: true };
  return { color: isDark ? "#4a6a8a" : "#c0d0e0", width: 1.5, dashed: false };
}

// ── Main component ──────────────────────────────────────────────────────────

interface TooltipState {
  visible: boolean;
  x: number;
  y: number;
  title: string;
  titleColor: string;
  rows: { label: string; value: string }[];
}

export function TopologyViewer() {
  const containerRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const networkRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const nodesSetRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const edgesSetRef = useRef<any>(null);
  const topoRef = useRef<TopologyData | null>(null);
  const dashOffsetRef = useRef(0);
  const animFrameRef = useRef<number>(0);
  const physicsOnRef = useRef(true);
  const isDarkRef = useRef(false);

  const [topo, setTopo] = useState<TopologyData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState<string>("all");
  const [tooltip, setTooltip] = useState<TooltipState>({
    visible: false,
    x: 0,
    y: 0,
    title: "",
    titleColor: "",
    rows: [],
  });

  // ── Dark mode detection ──────────────────────────────────────────────────
  const themeMode = usePreferencesStore((s) => s.themeMode);
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    if (themeMode === "dark") {
      setIsDark(true);
      isDarkRef.current = true;
      return;
    }
    if (themeMode === "light") {
      setIsDark(false);
      isDarkRef.current = false;
      return;
    }
    // system
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    setIsDark(mq.matches);
    isDarkRef.current = mq.matches;
    const handler = (e: MediaQueryListEvent) => {
      setIsDark(e.matches);
      isDarkRef.current = e.matches;
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [themeMode]);

  // ── Fetch topology ───────────────────────────────────────────────────────
  useEffect(() => {
    fetch("/api/topology")
      .then((r) => r.json())
      .then((data: TopologyData & { error?: string }) => {
        if (data.error) {
          setError(data.error);
          setLoading(false);
          return;
        }
        setTopo(data);
        topoRef.current = data;
        setLoading(false);
      })
      .catch((e) => {
        setError(String(e));
        setLoading(false);
      });
  }, []);

  // ── Build hull list from topology ────────────────────────────────────────

  // ── Initialize vis-network ───────────────────────────────────────────────
  useEffect(() => {
    if (!topo || !containerRef.current) return;

    let mounted = true;
    let localAnimFrame = 0;

    import("vis-network/standalone").then(({ Network, DataSet }) => {
      if (!mounted || !containerRef.current) return;

      const fontColors = isDarkRef.current ? FONT_COLORS_DARK : FONT_COLORS_LIGHT;

      const nodesData = topo.nodes.map((n: TopoNode) => ({
        id: n.id,
        label: n.label,
        group: n.group,
        shape: "image" as const,
        image: getNodeImage(n.id, n.group),
        size: getNodeSize(n.group),
        font: { color: fontColors[n.group] ?? "#ccc", face: "JetBrains Mono, monospace", size: 9 },
      }));

      let eid = 0;
      const edgesData = topo.links.map((l: TopoLink) => {
        const { color, width, dashed } = getEdgeColor(l.from, l.to, isDarkRef.current);
        return {
          id: eid++,
          from: l.from,
          to: l.to,
          title: `${l.from}:${l.fromPort} ↔ ${l.to}:${l.toPort}`,
          color: { color, highlight: "#00966a", hover: "#1a6fd4", opacity: 0.9 },
          width,
          dashes: dashed,
          smooth: { enabled: true, type: "dynamic", roundness: 0.5 },
          hoverWidth: width + 1.5,
          selectionWidth: width + 2,
        };
      });

      const nodes = new DataSet(nodesData);
      const edges = new DataSet(edgesData);
      nodesSetRef.current = nodes;
      edgesSetRef.current = edges;

      const network = new Network(
        containerRef.current!,
        { nodes, edges },
        {
          layout: { randomSeed: 12 },
          physics: {
            enabled: true,
            solver: "forceAtlas2Based",
            forceAtlas2Based: {
              gravitationalConstant: -28,
              centralGravity: 0.008,
              springLength: 60,
              springConstant: 0.12,
              damping: 0.6,
              avoidOverlap: 1.0,
            },
            stabilization: { iterations: 400, updateInterval: 30 },
          },
          interaction: {
            hover: true,
            tooltipDelay: 80,
            keyboard: { enabled: true, bindToWindow: false },
            multiselect: true,
          },
          nodes: { borderWidthSelected: 3 },
          edges: { selectionWidth: 3, hoverWidth: 2.5 },
        },
      );

      networkRef.current = network;

      network.once("stabilizationIterationsDone", () => {
        network.setOptions({ physics: { enabled: false } });
        physicsOnRef.current = false;
        network.fit({ animation: { duration: 900, easingFunction: "easeInOutQuad" } });
      });

      // Hull + animated dash drawing
      const mgmtEdgeIds = edgesData.filter((ed) => ed.dashes).map((ed) => ed.id);

      network.on("afterDrawing", (ctx: CanvasRenderingContext2D) => {
        const dark = isDarkRef.current;
        const scale = network.getScale();

        dashOffsetRef.current = (dashOffsetRef.current + 0.4) % 20;
        ctx.save();
        ctx.setLineDash([6, 6]);
        ctx.lineDashOffset = -dashOffsetRef.current;
        ctx.strokeStyle = dark ? "rgba(160,100,255,0.65)" : "rgba(124,58,237,0.55)";
        ctx.lineWidth = 2 / scale;

        for (const edgeId of mgmtEdgeIds) {
          const ed = edgesData[edgeId as number];
          if (!ed) continue;
          let fromPos: Point, toPos: Point;
          try {
            fromPos = network.getPosition(ed.from);
            toPos = network.getPosition(ed.to);
          } catch {
            continue;
          }
          ctx.beginPath();
          ctx.moveTo(fromPos.x, fromPos.y);
          ctx.lineTo(toPos.x, toPos.y);
          ctx.stroke();
        }
        ctx.restore();
      });

      // Continuous redraw for dash animation
      const animate = () => {
        network.redraw();
        localAnimFrame = requestAnimationFrame(animate);
        animFrameRef.current = localAnimFrame;
      };
      animate();

      // Hover tooltips
      const META: Record<string, { role: string; color: string }> = {
        bng: { role: "Broadband Network Gateway", color: "#00966a" },
        agg: { role: "Aggregation Switch", color: "#1a6fd4" },
        relay: { role: "Access Node (DHCP Relay)", color: "#0891b2" },
        service: { role: "Backend Service", color: "#7c3aed" },
        wan: { role: "WAN / Upstream", color: "#d4600a" },
        host: { role: "Subscriber CPE Host", color: "#4a6a8a" },
      };

      network.on("hoverNode", (p: { node: string; event: { center: { x: number; y: number } } }) => {
        const nd = nodesData.find((n) => n.id === p.node);
        if (!nd) return;
        const m = META[nd.group] ?? { role: nd.group, color: "#ccc" };
        const deg = network.getConnectedEdges(nd.id).length;
        setTooltip({
          visible: true,
          x: p.event.center.x + 16,
          y: p.event.center.y - 12,
          title: nd.id,
          titleColor: m.color,
          rows: [
            { label: "Role", value: m.role },
            { label: "Connections", value: String(deg) },
          ],
        });
      });

      network.on("blurNode", () => setTooltip((t) => ({ ...t, visible: false })));

      network.on("blurEdge", () => setTooltip((t) => ({ ...t, visible: false })));
    });

    return () => {
      mounted = false;
      cancelAnimationFrame(localAnimFrame);
      if (networkRef.current) {
        networkRef.current.destroy();
        networkRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topo]); // only re-init when topology changes

  // ── Update colors when isDark changes (without reinitialising) ───────────
  useEffect(() => {
    if (!networkRef.current || !nodesSetRef.current || !topoRef.current) return;
    const fontColors = isDark ? FONT_COLORS_DARK : FONT_COLORS_LIGHT;
    const updates = topoRef.current.nodes.map((n: TopoNode) => ({
      id: n.id,
      font: { color: fontColors[n.group] ?? "#ccc" },
    }));
    nodesSetRef.current.update(updates);

    // Also update edges
    if (edgesSetRef.current && topoRef.current) {
      let eid = 0;
      const edgeUpdates = topoRef.current.links.map((l: TopoLink) => {
        const { color, width, dashed } = getEdgeColor(l.from, l.to, isDark);
        return {
          id: eid++,
          color: { color, highlight: "#00966a", hover: "#1a6fd4", opacity: 0.9 },
          width,
          dashes: dashed,
          hoverWidth: width + 1.5,
          selectionWidth: width + 2,
        };
      });
      edgesSetRef.current.update(edgeUpdates);
    }
  }, [isDark]);

  // ── Control handlers ─────────────────────────────────────────────────────
  const fitView = () => networkRef.current?.fit({ animation: { duration: 600 } });

  const togglePhysics = () => {
    if (!networkRef.current) return;
    physicsOnRef.current = !physicsOnRef.current;
    networkRef.current.setOptions({ physics: { enabled: physicsOnRef.current } });
  };

  const resetLayout = () => {
    if (!networkRef.current) return;
    networkRef.current.setOptions({ physics: { enabled: true } });
    physicsOnRef.current = true;
    setTimeout(() => {
      if (!networkRef.current) return;
      networkRef.current.setOptions({ physics: { enabled: false } });
      physicsOnRef.current = false;
      networkRef.current.fit({ animation: true });
    }, 3500);
  };

  const showAll = () => {
    if (!networkRef.current || !nodesSetRef.current || !edgesSetRef.current || !topoRef.current) return;
    setActiveFilter("all");
    nodesSetRef.current.update(topoRef.current.nodes.map((n: TopoNode) => ({ id: n.id, hidden: false })));
    edgesSetRef.current.update(topoRef.current.links.map((l: TopoLink) => ({ id: l.id, hidden: false })));
    networkRef.current.fit({ animation: true });
  };

  const focusGroup = (g: string) => {
    if (!networkRef.current || !nodesSetRef.current || !edgesSetRef.current || !topoRef.current) return;
    setActiveFilter(g);
    const visible = new Set(topoRef.current.nodes.filter((n: TopoNode) => n.group === g).map((n: TopoNode) => n.id));
    for (const id of [...visible]) {
      for (const nb of networkRef.current.getConnectedNodes(id) as string[]) {
        visible.add(nb);
      }
    }
    nodesSetRef.current.update(topoRef.current.nodes.map((n: TopoNode) => ({ id: n.id, hidden: !visible.has(n.id) })));
    edgesSetRef.current.update(
      topoRef.current.links.map((l: TopoLink) => ({ id: l.id, hidden: !visible.has(l.from) || !visible.has(l.to) })),
    );
    networkRef.current.fit({ animation: true });
  };

  // ── Styles (dark-mode-aware) ─────────────────────────────────────────────
  const bg = isDark ? "bg-[#0a1520]" : "bg-[#f0f4f8]";
  const panel = isDark ? "bg-[#141e2f]/95 border-[#2a3a4a]" : "bg-white/95 border-[#c0d0e0]";
  const btnBase = isDark
    ? "border border-[#2a3a4a] bg-[#141e2f]/80 text-[#5a7a9a] hover:border-[#00966a] hover:text-[#00966a]"
    : "border border-[#c0d0e0] bg-white/80 text-[#6a8aa8] hover:border-[#00966a] hover:text-[#00966a]";
  const ttBg = isDark ? "bg-[#1a2030] border-[#2a3a4a] text-[#c8d8e8]" : "bg-white/95 border-[#c0d0e0] text-[#1a2a3a]";
  const ttDim = isDark ? "text-[#5a7a9a]" : "text-[#6a8aa8]";

  const LEGEND = [
    { color: "#00966a", label: "BNG" },
    { color: "#1a6fd4", label: "Aggregation" },
    { color: "#0891b2", label: "Access Node" },
    { color: "#7c3aed", label: "Services" },
    { color: "#d4600a", label: "WAN / Upstream" },
    { color: "#8aaac8", label: "Host (CPE)" },
  ];

  const FILTERS = [
    { key: "all", label: "ALL", action: showAll },
    { key: "bng", label: "BNG", action: () => focusGroup("bng") },
    { key: "agg", label: "AGG", action: () => focusGroup("agg") },
    { key: "relay", label: "ACCESS", action: () => focusGroup("relay") },
    { key: "service", label: "SERVICES", action: () => focusGroup("service") },
    { key: "host", label: "HOSTS", action: () => focusGroup("host") },
  ];

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div
      className={`flex flex-col h-full w-full ${bg} transition-colors duration-200`}
      style={{ fontFamily: "'JetBrains Mono', monospace" }}
    >
      {/* Header */}
      <header className={`flex items-center justify-between shrink-0 px-5 py-2 border-b ${panel} z-10`}>
        <div>
          <div
            style={{
              fontFamily: "'Orbitron', monospace",
              fontWeight: 900,
              fontSize: 18,
              letterSpacing: 5,
              color: "#00966a",
              textShadow: "0 0 10px #00966a33",
            }}
          >
          </div>
          <div
            style={{
              fontSize: 9,
              letterSpacing: 2,
              textTransform: "uppercase",
              color: isDark ? "#5a7a9a" : "#6a8aa8",
              marginTop: 2,
            }}
          >
            ISP Infrastructure · Containerlab Topology
          </div>
        </div>

        <div className="flex gap-3.5 items-center flex-wrap">
          {LEGEND.map((l) => (
            <div
              key={l.label}
              className="flex items-center gap-1.5"
              style={{
                fontSize: 9,
                color: isDark ? "#5a7a9a" : "#6a8aa8",
                letterSpacing: 1,
                textTransform: "uppercase",
              }}
            >
              <div style={{ width: 8, height: 8, borderRadius: 2, background: l.color }} />
              {l.label}
            </div>
          ))}
        </div>

        <div className="flex gap-4">
          <div className="flex flex-col items-end">
            <div style={{ fontFamily: "'Orbitron', monospace", fontSize: 13, fontWeight: 700, color: "#00966a" }}>
              {topo?.nodes.length ?? "—"}
            </div>
            <div
              style={{
                fontSize: 8,
                color: isDark ? "#5a7a9a" : "#6a8aa8",
                letterSpacing: 1,
                textTransform: "uppercase",
                marginTop: 1,
              }}
            >
              Nodes
            </div>
          </div>
          <div className="flex flex-col items-end">
            <div style={{ fontFamily: "'Orbitron', monospace", fontSize: 13, fontWeight: 700, color: "#00966a" }}>
              {topo?.links.length ?? "—"}
            </div>
            <div
              style={{
                fontSize: 8,
                color: isDark ? "#5a7a9a" : "#6a8aa8",
                letterSpacing: 1,
                textTransform: "uppercase",
                marginTop: 1,
              }}
            >
              Links
            </div>
          </div>
        </div>
      </header>

      {/* Canvas area */}
      <div className="flex-1 relative overflow-hidden">
        {/* Network container */}
        <div ref={containerRef} className="w-full h-full" />

        {/* Loading / error overlay */}
        {(loading || error) && (
          <div className={`absolute inset-0 flex items-center justify-center ${bg}`}>
            {loading && (
              <div
                style={{
                  color: isDark ? "#5a7a9a" : "#6a8aa8",
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 12,
                  letterSpacing: 2,
                }}
              >
                LOADING TOPOLOGY…
              </div>
            )}
            {error && (
              <div className="text-center max-w-md px-6">
                <div style={{ color: "#d4600a", fontFamily: "'Orbitron', monospace", fontSize: 13, marginBottom: 8 }}>
                  TOPOLOGY ERROR
                </div>
                <div style={{ color: isDark ? "#5a7a9a" : "#6a8aa8", fontSize: 10, lineHeight: 1.6 }}>{error}</div>
                <div style={{ color: isDark ? "#3a5a7a" : "#8aaac8", fontSize: 9, marginTop: 12, letterSpacing: 1 }}>
                  Set TOPOLOGY_YAML_PATH env var to your containerlab topology.yml path
                </div>
              </div>
            )}
          </div>
        )}

        {/* Filter buttons */}
        {!loading && !error && (
          <div className="absolute top-3 left-1/2 -translate-x-1/2 flex gap-1.5 z-30">
            {FILTERS.map((f) => (
              <button
                type="button"
                key={f.key}
                onClick={f.action}
                className="cursor-pointer transition-all duration-150"
                style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 9,
                  padding: "4px 10px",
                  letterSpacing: 1,
                  textTransform: "uppercase",
                  borderRadius: 2,
                  border: activeFilter === f.key ? "1px solid #00966a" : `1px solid ${isDark ? "#2a3a4a" : "#c0d0e0"}`,
                  background:
                    activeFilter === f.key
                      ? isDark
                        ? "#00966a18"
                        : "#00e5a010"
                      : isDark
                        ? "#141e2f/80"
                        : "rgba(255,255,255,0.8)",
                  color: activeFilter === f.key ? "#00966a" : isDark ? "#5a7a9a" : "#6a8aa8",
                }}
              >
                {f.label}
              </button>
            ))}
          </div>
        )}

        {/* Control buttons */}
        {!loading && !error && (
          <div className="absolute bottom-4 right-4 flex flex-col gap-1.5 z-30">
            {[
              { label: "⊞ Fit View", action: fitView },
              { label: "⚛ Toggle Physics", action: togglePhysics },
              { label: "↺ Reset Layout", action: resetLayout },
            ].map((b) => (
              <button
                type="button"
                key={b.label}
                onClick={b.action}
                className={`cursor-pointer transition-all duration-150 text-left ${btnBase}`}
                style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 9,
                  padding: "6px 12px",
                  letterSpacing: "1.5px",
                  textTransform: "uppercase",
                }}
              >
                {b.label}
              </button>
            ))}
          </div>
        )}

        {/* Tooltip */}
        {tooltip.visible && (
          <div
            className={`absolute pointer-events-none z-50 min-w-[190px] rounded-sm border shadow-lg px-3.5 py-2.5 ${ttBg}`}
            style={{ left: tooltip.x, top: tooltip.y, fontSize: 10 }}
          >
            <div
              style={{
                fontFamily: "'Orbitron', monospace",
                fontSize: 11,
                fontWeight: 700,
                marginBottom: 7,
                paddingBottom: 6,
                borderBottom: `1px solid ${isDark ? "#2a3a4a" : "#c0d0e0"}`,
                color: tooltip.titleColor,
              }}
            >
              {tooltip.title}
            </div>
            {tooltip.rows.map((r, i) => (
              <div key={i} className={`flex justify-between gap-3.5 mt-1 ${ttDim}`}>
                <span>{r.label}</span>
                {r.value && <span style={{ color: isDark ? "#c8d8e8" : "#1a2a3a" }}>{r.value}</span>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
