import { cn } from "@/lib/utils";

type PixelMascotProps = {
  className?: string;
  size?: number;
};

const PALETTE: Record<string, string> = {
  O: "#D9773E", // orange body
  D: "#A85A2A", // dark shade
  W: "#FFFFFF", // eye white
  B: "#2A1A11", // pupil
  C: "#FFCC99", // cheek highlight
};

const GRID = [
  "..O....O..",
  "....OO....",
  "...OOOO...",
  "..OWWWWO..",
  "..OWBBWO..",
  "...OOOO...",
  "..OOOOOO..",
  ".OOOOOOOO.",
  ".OO....OO.",
  "OOO....OOO",
];

export function PixelMascot({ className, size = 48 }: PixelMascotProps) {
  const rows = GRID.length;
  const cols = GRID[0].length;
  const cellSize = size / cols;

  return (
    <svg
      className={cn("inline-block", className)}
      width={size}
      height={cellSize * rows}
      viewBox={`0 0 ${cols} ${rows}`}
      xmlns="http://www.w3.org/2000/svg"
      shapeRendering="crispEdges"
    >
      {GRID.map((row, y) =>
        row.split("").map((ch, x) => {
          if (ch === "." || !PALETTE[ch]) return null;
          return (
            <rect
              key={`${x}-${y}`}
              x={x}
              y={y}
              width={1}
              height={1}
              fill={PALETTE[ch]}
            />
          );
        })
      )}
    </svg>
  );
}
