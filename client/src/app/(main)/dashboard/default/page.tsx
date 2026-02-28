import { Info, Server } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

import { BngHealthCards } from "./_components/bng-health-cards";
import { ChartAreaInteractive } from "./_components/chart-area-interactive";
import CustomersTable from "./_components/customers-table";
import RoutersTable from "./_components/routers-table";
import { SectionCards } from "./_components/section-cards";
import { SessionsTabs } from "./_components/sessions-tabs";
import { Shortcuts } from "./_components/shortcuts";
import { SimulateLabEnvironment } from "./_components/simulate-lab-environment";

export default function Page() {
  return (
    <div id="onborda-welcome" className="@container/main flex flex-col gap-4 md:gap-6">
      <Alert>
        <Info />
        <AlertTitle className="underline">DEMO Environment</AlertTitle>
        <AlertDescription className="inline-flex gap-1">
          The database resets every 12 hours or when triggered by a CI. The traffic simulation is configurable through{" "}
          <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">simulator.config.json</code>
          <br />
          The lab can also be run locally in the VM using Vagrant.
        </AlertDescription>
      </Alert>
      <SectionCards />
      <Shortcuts />
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
          <SessionsTabs />
          <div id="routers-section" className="min-w-0">
            <RoutersTable />
          </div>
        </div>

      </div>
    </div>
  );
}
