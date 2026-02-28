import { Info, Server } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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

export default function Page() {
  return (
    <div id="onborda-welcome" className="@container/main flex flex-col gap-4 md:gap-6">
      <Alert>
        <Info />
        <AlertTitle className="underline">DEMO Environment</AlertTitle>
        <AlertDescription className="inline-flex gap-1">
          The database is reset every 12 hours. The traffic simulation is configurable through{" "}
          <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">simulator.config.json</code>
        </AlertDescription>
      </Alert>
      <SectionCards />
      <div className="flex @5xl/main:flex-row flex-col gap-4 items-start">
        {/* Main Content Column */}
        <div className="flex flex-col gap-4 md:gap-6 flex-1 min-w-0">
          <div className="flex gap-4 flex-col lg:flex-row">
            <div className="flex-8 min-w-0">
              <CustomersTable />
            </div>
            <div className="flex flex-col gap-4 @5xl/main:w-sm w-full shrink-0 lg:mt-16">
              <SimulateLabEnvironment />
            </div>
          </div>
          <span className="text-2xl font-bold inline-flex items-center gap-2">
            <Server className="inline-block h-5 w-5 mr-1" />
            Broadband Network Gateways ( BNGs )
          </span>
          <div className="min-w-0">
            <BngHealthCards />
          </div>
          <div className="min-w-0">
            <ChartAreaInteractive />
          </div>
          <Tabs defaultValue="active" className="w-full min-w-0">
            <TabsList>
              <TabsTrigger value="active">Active Sessions</TabsTrigger>
              <TabsTrigger value="history">Session History</TabsTrigger>
              <TabsTrigger value="events">Events</TabsTrigger>
            </TabsList>
            <TabsContent value="active" className="min-w-0">
              <SessionsTable />
            </TabsContent>
            <TabsContent value="history" className="min-w-0">
              <SessionsHistoryTable />
            </TabsContent>
            <TabsContent value="events" className="min-w-0">
              <SessionsEventsTable />
            </TabsContent>
          </Tabs>
          <div className="min-w-0">
            <RoutersTable />
          </div>
        </div>

      </div>
    </div>
  );
}
