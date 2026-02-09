import { ChartAreaInteractive } from "./_components/chart-area-interactive";
import SessionsTable from "./_components/sessions-table";
import SessionsHistoryTable from "./_components/sessions-history-table";
import SessionsEventsTable from "./_components/sessions-events-table";
import RoutersTable from "./_components/routers-table";
import { SectionCards } from "./_components/section-cards";
import Logo from "@/components/logo";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function Page() {
  return (
    <div className="@container/main flex flex-col gap-4 md:gap-6">
      <div className="flex gap-2 items-baseline">
        <Logo height={100} width={100} variant="isolated-monochrome-black" className="dark:invert"/>
        <span className="text-lg font-light">| OSS Dashboard</span>
      </div>
      <SectionCards />
      {/* <ChartAreaInteractive /> */}
      <Tabs defaultValue="active" className="w-full">
        <TabsList>
          <TabsTrigger value="active">Active Sessions</TabsTrigger>
          <TabsTrigger value="history">Session History</TabsTrigger>
          <TabsTrigger value="events">Events</TabsTrigger>
        </TabsList>
        <TabsContent value="active">
          <SessionsTable />
        </TabsContent>
        <TabsContent value="history">
          <SessionsHistoryTable />
        </TabsContent>
        <TabsContent value="events">
          <SessionsEventsTable />
        </TabsContent>
      </Tabs>
      <RoutersTable />
    </div>
  );
}
