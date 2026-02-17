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
import { SimulateLabEnvironment } from "./_components/simulate-lab-environment";
import { TopAlerts } from "./_components/top-alerts";

export default function Page() {
  return (
    <div className="@container/main flex flex-col gap-4 md:gap-6">
      <SectionCards />
      <div className="flex @5xl/main:flex-row flex-col gap-4 items-start">
        {/* Main Content Column */}
        <div className="flex flex-col gap-4 md:gap-6 flex-1 min-w-0">
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

        {/* Right Sidebar */}
        <div className="flex flex-col gap-4 @5xl/main:w-sm w-full shrink-0">
          <SimulateLabEnvironment />
          <TopAlerts />
        </div>
      </div>
    </div>
  );
}
