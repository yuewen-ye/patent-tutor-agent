import { cn } from "@/lib/utils";

type DeskSceneProps = {
  className?: string;
};

export function DeskScene({ className }: DeskSceneProps) {
  return (
    <svg
      className={cn("w-full h-full", className)}
      viewBox="0 0 800 600"
      preserveAspectRatio="xMidYMid slice"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <linearGradient id="wall" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#FFF9F0" />
          <stop offset="100%" stopColor="#FFE8D0" />
        </linearGradient>
        <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#BAE6FD" />
          <stop offset="100%" stopColor="#FFFFFF" />
        </linearGradient>
        <linearGradient id="deskTop" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#E8B88A" />
          <stop offset="100%" stopColor="#D4A373" />
        </linearGradient>
        <linearGradient id="lampLight" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#FFD700" stopOpacity="0.25" />
          <stop offset="100%" stopColor="#FFD700" stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* Wall & floor */}
      <rect width="800" height="600" fill="url(#wall)" />
      <rect x="0" y="450" width="800" height="150" fill="#F3DFCC" />
      <rect x="0" y="450" width="800" height="10" fill="#E5C9AB" />

      {/* Window */}
      <rect x="440" y="50" width="280" height="240" rx="12" fill="#8B5E3C" />
      <rect x="450" y="60" width="260" height="220" rx="8" fill="url(#sky)" />
      <circle cx="510" cy="110" r="35" fill="#FFFFFF" opacity="0.9" />
      <circle cx="600" cy="95" r="28" fill="#FFFFFF" opacity="0.85" />
      <circle cx="650" cy="140" r="22" fill="#FFFFFF" opacity="0.8" />
      {/* Tree outside */}
      <circle cx="670" cy="200" r="55" fill="#86EFAC" opacity="0.9" />
      <circle cx="720" cy="170" r="45" fill="#4ADE80" opacity="0.85" />
      <rect x="690" y="240" width="20" height="80" fill="#A16207" />
      {/* Window sill */}
      <rect x="430" y="285" width="300" height="18" rx="4" fill="#E8B88A" />

      {/* Sticky notes on the wall */}
      <g transform="rotate(-6 100 120)">
        <rect x="80" y="80" width="70" height="70" rx="2" fill="#FBCFE8" />
        <rect x="95" y="100" width="40" height="4" rx="2" fill="#F472B6" opacity="0.5" />
        <rect x="95" y="115" width="30" height="4" rx="2" fill="#F472B6" opacity="0.5" />
      </g>
      <g transform="rotate(4 180 130)">
        <rect x="160" y="90" width="65" height="65" rx="2" fill="#FDE68A" />
        <rect x="175" y="110" width="35" height="4" rx="2" fill="#F59E0B" opacity="0.5" />
      </g>
      <g transform="rotate(-3 120 200)">
        <rect x="100" y="170" width="60" height="60" rx="2" fill="#BBF7D0" />
        <rect x="115" y="190" width="30" height="4" rx="2" fill="#22C55E" opacity="0.5" />
      </g>

      {/* Desk */}
      <polygon points="70,440 730,440 690,470 110,470" fill="url(#deskTop)" />
      <rect x="120" y="470" width="24" height="140" rx="4" fill="#9A6B4A" />
      <rect x="656" y="470" width="24" height="140" rx="4" fill="#9A6B4A" />

      {/* Books */}
      <rect x="95" y="415" width="70" height="25" rx="3" fill="#3B82F6" />
      <rect x="100" y="410" width="70" height="25" rx="3" fill="#10B981" />
      <rect x="90" y="420" width="70" height="20" rx="3" fill="#F59E0B" />
      <rect x="95" y="417" width="50" height="4" rx="2" fill="#FFFFFF" opacity="0.4" />
      <rect x="100" y="412" width="50" height="4" rx="2" fill="#FFFFFF" opacity="0.4" />
      <rect x="90" y="422" width="50" height="3" rx="1.5" fill="#FFFFFF" opacity="0.4" />

      {/* Desk lamp */}
      <ellipse cx="200" cy="455" rx="35" ry="10" fill="#525252" />
      <path
        d="M190 455 L180 380 L200 370 L215 455"
        stroke="#525252"
        strokeWidth="8"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M170 370 L230 370 L245 340 L155 340 Z" fill="#404040" />
      <polygon points="155,340 245,340 280,455 120,455" fill="url(#lampLight)" />

      {/* Laptop */}
      <path d="M280 455 L520 455 L540 470 L260 470 Z" fill="#A3A3A3" />
      <rect x="300" y="340" width="200" height="120" rx="8" fill="#262626" />
      <rect x="308" y="348" width="184" height="104" rx="4" fill="#171717" />
      {/* Code lines */}
      <rect x="320" y="360" width="80" height="4" rx="2" fill="#4ADE80" />
      <rect x="320" y="372" width="120" height="4" rx="2" fill="#A7D8F5" />
      <rect x="320" y="384" width="100" height="4" rx="2" fill="#FFFFFF" />
      <rect x="320" y="396" width="60" height="4" rx="2" fill="#F472B6" />
      <rect x="320" y="408" width="90" height="4" rx="2" fill="#4ADE80" />
      <rect x="320" y="420" width="70" height="4" rx="2" fill="#A7D8F5" />
      {/* Simple graph on screen */}
      <polyline
        points="330,430 350,415 370,425 390,405 410,410"
        fill="none"
        stroke="#D9773E"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="330" cy="430" r="3" fill="#D9773E" />
      <circle cx="350" cy="415" r="3" fill="#D9773E" />
      <circle cx="370" cy="425" r="3" fill="#D9773E" />
      <circle cx="390" cy="405" r="3" fill="#D9773E" />
      <circle cx="410" cy="410" r="3" fill="#D9773E" />

      {/* Plant */}
      <path d="M610 470 L650 470 L640 430 L620 430 Z" fill="#D9773E" />
      <ellipse cx="630" cy="430" rx="35" ry="8" fill="#7C2D12" />
      <circle cx="610" cy="405" r="25" fill="#22C55E" />
      <circle cx="645" cy="395" r="22" fill="#4ADE80" />
      <circle cx="630" cy="370" r="20" fill="#86EFAC" />
      <circle cx="600" cy="385" r="18" fill="#16A34A" />

      {/* Mug */}
      <path d="M690 445 L690 470 L720 470 L720 445 Z" fill="#FFFFFF" />
      <ellipse cx="705" cy="445" rx="15" ry="5" fill="#E5E5E5" />
      <path
        d="M720 450 Q730 450 730 460 Q730 468 720 468"
        stroke="#E5E5E5"
        strokeWidth="4"
        fill="none"
      />
      <rect x="700" y="438" width="10" height="12" rx="2" fill="#D9773E" opacity="0.8" />
    </svg>
  );
}
