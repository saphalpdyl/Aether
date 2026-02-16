import { Server } from "lucide-react";

import Logo from "@/components/logo";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { BngHealthCards } from "./_components/bng-health-cards";
import { ChartAreaInteractive } from "./_components/chart-area-interactive";
import CustomersTable from "./_components/customers-table";
import RoutersTable from "./_components/routers-table";
import { SectionCards } from "./_components/section-cards";
import SessionsEventsTable from "./_components/sessions-events-table";
import SessionsHistoryTable from "./_components/sessions-history-table";
import SessionsTable from "./_components/sessions-table";

export default function Page() {
  return (
    <div className="@container/main flex flex-col gap-4 md:gap-6">
      <div className="flex gap-2 items-baseline">
        <Logo height={100} width={100} variant="isolated-monochrome-black" className="dark:invert" />
        <span className="text-lg font-light">| OSS Dashboard</span>
      </div>
      <SectionCards />
      <CustomersTable />
      <span className="text-2xl font-bold inline-flex items-center gap-2">
        <Server className="inline-block h-5 w-5 mr-1" />
        Broadband Network Gateways ( BNGs )
      </span>
      <BngHealthCards />
      <ChartAreaInteractive />
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
