import packageJson from "../../package.json";

const currentYear = new Date().getFullYear();

export const APP_CONFIG = {
  name: "Aether",
  version: packageJson.version,
  copyright: `© ${currentYear}, saphalpdyl.`,
  meta: {
    title: "Aether - Open-Source ISP Orchaestration Lab",
    description:
      "Aether is a modern, open-source ISP orchestration lab built with custom BNG, Access Routers and other network components.",
  },
};
