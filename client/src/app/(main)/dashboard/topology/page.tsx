import { TopologyViewer } from "./_components/topology-viewer";
import { getTopology } from "@/server/server-actions";

export default async function TopologyPage() {
  const topologyData = await getTopology();

  return (
    <div className="-m-4 md:-m-6 h-[calc(100vh-3.5rem)] overflow-hidden">
      <TopologyViewer initialData={topologyData} />
    </div>
  );
}
