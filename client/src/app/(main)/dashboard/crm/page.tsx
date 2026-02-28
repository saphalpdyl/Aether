import { Suspense } from "react";

import ProvisioningConsole from "./_components/provisioning-console";

export default function Page() {
  return (
    <Suspense>
      <ProvisioningConsole />
    </Suspense>
  );
}
