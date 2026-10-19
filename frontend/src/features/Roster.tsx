import { useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { ReactNode } from "react";
export default function Roster({
  count,
  row,
}: {
  count: number;
  row: (index: number) => ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const virtual = useVirtualizer({
    count: count > 100 ? count : 0,
    getScrollElement: () => ref.current,
    estimateSize: () => 96,
    overscan: 5,
  });
  if (count <= 100)
    return (
      <div>
        {Array.from({ length: count }, (_, i) => (
          <div key={i}>{row(i)}</div>
        ))}
      </div>
    );
  return (
    <div ref={ref} style={{ height: 540, overflow: "auto" }}>
      <div style={{ height: virtual.getTotalSize(), position: "relative" }}>
        {virtual.getVirtualItems().map((item) => (
          <div
            key={item.key}
            ref={virtual.measureElement}
            data-index={item.index}
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              transform: `translateY(${item.start}px)`,
            }}
          >
            {row(item.index)}
          </div>
        ))}
      </div>
    </div>
  );
}
