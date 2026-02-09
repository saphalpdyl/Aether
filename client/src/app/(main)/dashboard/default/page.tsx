import { ChartAreaInteractive } from "./_components/chart-area-interactive";
import SessionsTable from "./_components/sessions-table";
import { SectionCards } from "./_components/section-cards";
import Logo from "@/components/logo";

export default function Page() {
  return (
    <div className="@container/main flex flex-col gap-4 md:gap-6">
      <div className="flex gap-2 items-baseline">
        <Logo height={100} width={100} variant="isolated-monochrome-black" className="dark:invert"/>
        <span className="text-lg font-light">| OSS Dashboard</span>
      </div>
  {/* <SectionCards /> */}
  {/* <ChartAreaInteractive /> */}
  <SessionsTable />
    </div>
  );
}
