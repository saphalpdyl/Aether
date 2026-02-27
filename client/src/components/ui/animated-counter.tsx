"use client";

import { useEffect, useRef, useState } from "react";
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
  invertColors?: boolean;
}

function useComputedColor(ref: React.RefObject<HTMLElement | null>) {
  const [color, setColor] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (!ref.current) return;
    const computed = getComputedStyle(ref.current).color;
    setColor(computed);

    const observer = new MutationObserver(() => {
      if (ref.current) {
        setColor(getComputedStyle(ref.current).color);
      }
    });
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class", "style", "data-theme"],
    });
    return () => observer.disconnect();
  }, [ref]);

  return color;
}

export function AnimatedCounter({
  value,
  fontSize = "24px",
  color,
  incrementColor = "#32cd32",
  decrementColor = "#fe6862",
  decimals = 0,
  includeCommas = false,
  suffix,
  prefix,
  invertColors = false,
}: AnimatedCounterProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const computedColor = useComputedColor(containerRef);
  const resolvedColor = color ?? computedColor ?? "black";

  return (
    <div ref={containerRef} className="inline-flex items-baseline">
      {prefix && <span>{prefix}</span>}
      <ReactAnimatedCounter
        value={value}
        fontSize={fontSize}
        color={resolvedColor}
        incrementColor={invertColors ? decrementColor : incrementColor}
        decrementColor={invertColors ? incrementColor : decrementColor}
        includeDecimals={decimals > 0}
        decimalPrecision={decimals}
        includeCommas={includeCommas}
      />
      {suffix && <span>{suffix}</span>}
    </div>
  );
}
