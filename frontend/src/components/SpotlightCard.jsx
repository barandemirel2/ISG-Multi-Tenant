import React, { useRef, useState } from 'react';
import { cn } from "@/lib/utils";

export const SpotlightCard = ({
  children,
  className = "",
  spotlightColor = "rgba(239, 68, 68, 0.4)", // Opaklık %40'a çıkarıldı
  ...rest
}) => {
  const divRef = useRef(null);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [opacity, setOpacity] = useState(0);

  const handleMouseMove = (e) => {
    if (!divRef.current) return;
    const rect = divRef.current.getBoundingClientRect();
    setPosition({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  };

  return (
    <div
      ref={divRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setOpacity(1)}
      onMouseLeave={() => setOpacity(0)}
      className={cn(
        "relative overflow-hidden rounded-card border border-slate-200/80 dark:border-white/10 bg-white dark:bg-slate-950/80 text-slate-900 dark:text-slate-100 p-5 shadow-sm dark:shadow-2xl transition-all duration-300 hover:border-slate-300 dark:hover:border-white/20",
        className
      )}
      {...rest}
    >
      {/* CANLI SPOT IŞIĞI KATMANI */}
      <div
        className="pointer-events-none absolute -inset-px transition-opacity duration-200"
        style={{
          opacity,
          background: `radial-gradient(400px circle at ${position.x}px ${position.y}px, ${spotlightColor}, transparent 70%)`,
        }}
      />
      <div className="relative z-10">{children}</div>
    </div>
  );
};
