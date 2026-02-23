"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

interface AnimatedCounterProps {
  value: number;
  className?: string;
  duration?: number;
  decimals?: number;
  separator?: string;
  suffix?: string;
  prefix?: string;
}

function DialDigit({ value, duration = 0.6 }: { value: number; duration?: number }) {
  const [displayValue, setDisplayValue] = useState(value);
  const [isAnimating, setIsAnimating] = useState(false);

  useEffect(() => {
    if (value !== displayValue) {
      setIsAnimating(true);
      // Small delay to ensure the exit animation starts
      const startTimeout = setTimeout(() => {
        setDisplayValue(value);
      }, 50);
      
      // Reset animation state after animation completes
      const endTimeout = setTimeout(() => {
        setIsAnimating(false);
      }, duration * 1000 + 50);
      
      return () => {
        clearTimeout(startTimeout);
        clearTimeout(endTimeout);
      };
    }
  }, [value, displayValue, duration]);

  return (
    <span className="inline-block relative overflow-hidden align-baseline" style={{ minWidth: "0.65em", height: "1.2em" }}>
      {isAnimating && (
        <span
          key={`exit-${displayValue}`}
          className="absolute inset-0 flex items-center justify-center animate-roll-up-exit"
          style={{
            animationDuration: `${duration}s`,
          }}
        >
          {displayValue}
        </span>
      )}
      <span
        key={`enter-${value}`}
        className={cn(
          "inline-flex items-center justify-center w-full",
          isAnimating && "animate-roll-up-enter"
        )}
        style={{
          animationDuration: `${duration}s`,
        }}
      >
        {isAnimating ? value : displayValue}
      </span>
    </span>
  );
}

export function AnimatedCounter({
  value,
  className = "",
  duration = 0.6,
  decimals = 0,
  separator = ",",
  suffix = "",
  prefix = "",
}: AnimatedCounterProps) {
  const formattedValue = value.toFixed(decimals);
  const [integerPart, decimalPart] = formattedValue.split(".");
  
  // Add thousands separators
  const withSeparators = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, separator);
  
  return (
    <span className={cn("inline-flex items-baseline", className)}>
      {prefix && <span className="mr-0.5">{prefix}</span>}
      <span className="inline-flex items-baseline">
        {withSeparators.split("").map((char, index) => {
          if (char === separator) {
            return <span key={`sep-${index}`} className="mx-0.5">{char}</span>;
          }
          return <DialDigit key={`digit-${index}`} value={parseInt(char)} duration={duration} />;
        })}
      </span>
      {decimals > 0 && decimalPart && (
        <>
          <span className="mx-0.5">.</span>
          <span className="inline-flex items-baseline">
            {decimalPart.split("").map((char, index) => (
              <DialDigit key={`decimal-${index}`} value={parseInt(char)} duration={duration} />
            ))}
          </span>
        </>
      )}
      {suffix && <span className="ml-0.5">{suffix}</span>}
    </span>
  );
}
