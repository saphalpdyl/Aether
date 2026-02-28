import { TopologyData } from "@/app/api/topology/route";
import { TopologyViewer } from "./_components/topology-viewer";
import { getTopology } from "@/server/server-actions";

export const dynamic = "force-dynamic";

export default async function TopologyPage() {
  const topologyData = await getTopology();

  if (!topologyData || "error" in topologyData) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-3.5rem)]">
        <p className="text-gray-500">Failed to load topology data.</p>
      </div>
    );
  }

  return (
    <div className="-m-4 md:-m-6 h-[calc(100vh-3.5rem)] overflow-hidden">
      <TopologyViewer initialData={topologyData as TopologyData} />
    </div>
  );
}
