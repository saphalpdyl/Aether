import { BookOpen, Info, Server } from "lucide-react";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
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
          The lab resets every 6 hours or when triggered by a CI. The traffic simulation is configurable through simulator.config.json
          The lab can also be run locally in the VM using Vagrant.
        </AlertDescription>
      </Alert>
      <div className="rounded-lg border bg-card text-card-foreground shadow-sm">
        <Accordion type="single" collapsible>
          <AccordionItem value="getting-started" className="border-b-0">
            <AccordionTrigger className="px-4">
              <span className="inline-flex items-center gap-2">
                <BookOpen className="h-4 w-4" />
                Getting Started — How to Emulate a Subscriber Lifecycle
              </span>
            </AccordionTrigger>
            <AccordionContent className="px-4">
              <p className="text-muted-foreground mb-4">
                Follow these steps to create a customer, provision a service, bring them online, and run a throughput test.
              </p>
              <ol className="list-decimal list-outside space-y-3 pl-5 text-sm">
                <li>
                  <strong>Create a customer.</strong> Use the{" "}
                  <em>&quot;Add customer&quot;</em> shortcut in the Shortcuts bar below.
                  Fill in the customer details and save.
                </li>
                <li>
                  <strong>Navigate to the customer.</strong> Back on the Dashboard,
                  find your new customer in the <em>Customers</em> table and click
                  their name to open the customer details page.
                </li>
                <li>
                  <strong>Add a service.</strong> On the customer details page, scroll to
                  the <em>Services</em> section and click <em>&quot;Add Service&quot;</em>.
                </li>
                <li>
                  <strong>Provision a port.</strong> In the modal that opens, select a{" "}
                  <strong>BNG</strong> and an <strong>Access Router</strong>. The
                  available ports will appear — click any{" "}
                  <span className="text-green-600 font-semibold">green (Available)</span>{" "}
                  port. Then choose a <em>Service Plan</em> (default plans are
                  provided) and click <em>&quot;Provision Service&quot;</em>.
                </li>
                <li>
                  <strong>Select the customer service for simulation.</strong> Back on
                  the Dashboard, look at the <em>Simulate Lab Environment</em> panel on
                  the right. In the <em>Customer Service</em> dropdown, select your
                  customer&apos;s service (shown as{" "}
                  <em>&quot;Customer Name - Plan Name&quot;</em>, e.g.{" "}
                  <em>&quot;Pine Ridge School - Gold 300/100&quot;</em>).
                </li>
                <li>
                  <strong>Bring the customer online (DHCP).</strong> Set the{" "}
                  <em>Command Group</em> to <strong>DHCP INIT</strong> and select the
                  command <strong>&quot;Request DHCP lease&quot;</strong>. Click{" "}
                  <em>&quot;Simulate Subscriber&quot;</em>. After a few seconds, the
                  output will show an IP address being assigned and the customer&apos;s
                  status will change from <em>Offline</em> to{" "}
                  <span className="text-green-600 font-semibold">Online</span> in the
                  Customers table.
                </li>
                <li>
                  <strong>Run a throughput test.</strong> With the same customer service
                  selected, change the <em>Command Group</em> to{" "}
                  <strong>IPERF3 DEMO</strong> and pick either{" "}
                  <em>&quot;Upload throughput test&quot;</em> or{" "}
                  <em>&quot;Download throughput test&quot;</em>. Click{" "}
                  <em>&quot;Simulate Subscriber&quot;</em>. The test runs for about 10
                  seconds. When it finishes, expand the output to see the iperf3 results
                  with the aggregate throughput rate at the bottom.
                  <br />
                  <span className="text-muted-foreground text-xs">
                    Note: The test may fail if other users are running a test at
                    the same time.
                  </span>
                </li>
                <li>
                  <strong>View session data.</strong> Scroll down to see{" "}
                  <em>Active Sessions</em>, <em>Session History</em> (sessions that
                  have been stopped), and <em>Session Events</em> (all RADIUS updates
                  including authorization, session start, and session stop).
                </li>
                <li>
                  <strong>Release the session (go offline).</strong> To stop a
                  subscriber session, go back to the <em>Simulate Lab Environment</em>{" "}
                  panel, select the customer service, set the <em>Command Group</em> to{" "}
                  <strong>DHCP RELEASE</strong>, select{" "}
                  <strong>&quot;Release DHCP lease&quot;</strong>, and click{" "}
                  <em>&quot;Simulate Subscriber&quot;</em>. The session will end and the
                  customer will go back to <em>Offline</em>.
                </li>
              </ol>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </div>
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
