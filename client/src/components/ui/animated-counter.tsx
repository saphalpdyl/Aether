"use client";

import { AnimatedCounter as ReactAnimatedCounter } from "react-animated-counter";

interface AnimatedCounterProps {
  value: number;
  fontSize?: string;
  color?: string;
  incrementColor?: string;
  decrementColor?: string;
  decimals?: number;
  includeCommas?: boolean;
  suffix?: string;
  prefix?: string;
}

export function AnimatedCounter({
  value,
  fontSize,
  color,
  incrementColor = "#32cd32",
  decrementColor = "#fe6862",
  decimals = 0,
  includeCommas = false,
  suffix,
  prefix,
}: AnimatedCounterProps) {
  return (
    <div className="inline-flex items-baseline">
      {prefix && <span>{prefix}</span>}
      <ReactAnimatedCounter
        value={value}
        fontSize={"24px"}
        color={color}
        incrementColor={incrementColor}
        decrementColor={decrementColor}
        includeDecimals={true}
        decimalPrecision={1}
        includeCommas={includeCommas}
      />
      {suffix && <span>{suffix}</span>}
    </div>
  );
}
