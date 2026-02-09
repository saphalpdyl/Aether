import Image from "next/image";
import defaultSvg from "@/assets/logo/vector/default.svg";
import defaultMonochrome from "@/assets/logo/vector/default-monochrome.svg";
import defaultMonochromeBlack from "@/assets/logo/vector/default-monochrome-black.svg";
import defaultMonochromeWhite from "@/assets/logo/vector/default-monochrome-white.svg";
import isolatedLayout from "@/assets/logo/vector/isolated-layout.svg";
import isolatedMonochromeBlack from "@/assets/logo/vector/isolated-monochrome-black.svg";
import isolatedMonochromeWhite from "@/assets/logo/vector/isolated-monochrome-white.svg";
import coverPng from "@/assets/logo/cover.png";
import defaultPng from "@/assets/logo/default.png";
import profilePng from "@/assets/logo/profile.png";

type LogoVariant =
  | "default"
  | "default-monochrome"
  | "default-monochrome-black"
  | "default-monochrome-white"
  | "isolated-layout"
  | "isolated-monochrome-black"
  | "isolated-monochrome-white"
  | "cover"
  | "default-png"
  | "profile";

interface LogoProps {
  variant?: LogoVariant;
  width?: number;
  height?: number;
  className?: string;
  priority?: boolean;
}

const logoMap = {
  default: defaultSvg,
  "default-monochrome": defaultMonochrome,
  "default-monochrome-black": defaultMonochromeBlack,
  "default-monochrome-white": defaultMonochromeWhite,
  "isolated-layout": isolatedLayout,
  "isolated-monochrome-black": isolatedMonochromeBlack,
  "isolated-monochrome-white": isolatedMonochromeWhite,
  cover: coverPng,
  "default-png": defaultPng,
  profile: profilePng,
} as const;

export default function Logo({
  variant = "default",
  width = 120,
  height = 40,
  className,
  priority = false,
}: LogoProps) {
  const logoSrc = logoMap[variant];

  return (
    <Image
      src={logoSrc}
      alt="Logo"
      width={width}
      height={height}
      className={className}
      priority={priority}
    />
  );
}