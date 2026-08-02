import { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface MasteryHeatmapProps {
  mastery?: Record<string, number>;
}

interface CategoryConfig {
  key: string;
  label: string;
  color: string;
  bgLight: string;
  filter: (k: string) => boolean;
}

const categories: CategoryConfig[] = [
  {
    key: "patent-law",
    label: "专利法",
    color: "#4a8c74",
    bgLight: "rgba(74, 140, 116, 0.12)",
    filter: (k) => k.startsWith("patent-") && !k.includes("examination"),
  },
  {
    key: "examination",
    label: "专利审查指南",
    color: "#8b7355",
    bgLight: "rgba(139, 115, 85, 0.12)",
    filter: (k) => k.includes("examination"),
  },
  {
    key: "practice",
    label: "专利代理实务",
    color: "#c8956c",
    bgLight: "rgba(200, 149, 108, 0.12)",
    filter: (k) => k.includes("practice") || k.includes("drafting") || k.includes("agent"),
  },
  {
    key: "related-laws",
    label: "相关法律知识",
    color: "#6b8a9e",
    bgLight: "rgba(107, 138, 158, 0.12)",
    filter: (k) => k.includes("related") || k.includes("civil") || k.includes("contract") || k.includes("law"),
  },
];

interface NodePosition {
  id: string;
  label: string;
  value: number;
  category: CategoryConfig;
  x: number;
  y: number;
  r: number;
}

const VIEW_W = 520;
const VIEW_H = 380;
const CX = VIEW_W / 2;
const CY = VIEW_H / 2;

function layoutNodes(mastery: Record<string, number>): {
  nodes: NodePosition[];
  edges: [number, number][];
} {
  const entries = Object.entries(mastery);
  if (entries.length === 0) return { nodes: [], edges: [] };

  const sectorAngle = (2 * Math.PI) / categories.length;
  const nodes: NodePosition[] = [];

  categories.forEach((cat, catIdx) => {
    const items = entries.filter(([k]) => cat.filter(k));
    if (items.length === 0) return;

    const baseAngle = catIdx * sectorAngle - Math.PI / 2;
    const spread = Math.min(sectorAngle * 0.85, sectorAngle * 0.6 + items.length * 0.08);

    items.forEach(([id, val], i) => {
      const t = items.length === 1 ? 0.5 : i / (items.length - 1);
      const angle = baseAngle - spread / 2 + spread * t;
      const radiusBase = 95 + (1 - val) * 45;
      const radiusJitter = ((i * 7 + catIdx * 13) % 17) * 3;
      const r = radiusBase + radiusJitter;

      const x = CX + Math.cos(angle) * r;
      const y = CY + Math.sin(angle) * r;
      const nodeR = 4 + val * 12;

      nodes.push({
        id,
        label: id.replace(/-/g, " ").replace(/^./, (c) => c.toUpperCase()),
        value: val,
        category: cat,
        x,
        y,
        r: nodeR,
      });
    });
  });

  const edges: [number, number][] = [];
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      if (nodes[i].category.key === nodes[j].category.key) {
        const dx = nodes[i].x - nodes[j].x;
        const dy = nodes[i].y - nodes[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 120) {
          edges.push([i, j]);
        }
      }
    }
  }

  return { nodes, edges };
}

function getNodeFill(value: number): string {
  if (value >= 0.85) return "#4a8c74";
  if (value >= 0.6) return "#7ba696";
  if (value >= 0.35) return "#d4a574";
  return "#c47a7a";
}

function getNodeStroke(value: number): string {
  if (value >= 0.85) return "#3a7060";
  if (value >= 0.6) return "#6a8f80";
  if (value >= 0.35) return "#b89060";
  return "#a86060";
}

function getNodeBg(value: number): string {
  if (value >= 0.85) return "rgba(74, 140, 116, 0.15)";
  if (value >= 0.6) return "rgba(123, 166, 150, 0.15)";
  if (value >= 0.35) return "rgba(212, 165, 116, 0.15)";
  return "rgba(196, 122, 122, 0.15)";
}

export function MasteryHeatmap({ mastery }: MasteryHeatmapProps) {
  const [hovered, setHovered] = useState<NodePosition | null>(null);

  const layout = useMemo(() => {
    if (!mastery) return { nodes: [], edges: [] };
    return layoutNodes(mastery);
  }, [mastery]);

  const hasMastery = mastery && Object.keys(mastery).length > 0;

  const categoryStats = useMemo(() => {
    if (!mastery) return [];
    return categories.map((cat) => {
      const keys = Object.keys(mastery).filter((k) => cat.filter(k));
      const avg = keys.length > 0 ? keys.reduce((s, k) => s + mastery[k], 0) / keys.length : 0;
      return { ...cat, avg, count: keys.length };
    });
  }, [mastery]);

  const bgDots = useMemo(() => {
    const dots: { x: number; y: number; r: number; o: number }[] = [];
    for (let i = 0; i < 40; i++) {
      dots.push({
        x: Math.random() * VIEW_W,
        y: Math.random() * VIEW_H,
        r: Math.random() * 1.5 + 0.5,
        o: Math.random() * 0.08 + 0.02,
      });
    }
    return dots;
  }, []);

  return (
    <Card className="border-border/40 bg-card shadow-soft">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-medium flex items-center gap-2">
          <span>掌握度星图</span>
          <span className="text-xs text-muted-foreground font-normal">
            · {layout.nodes.length} 个知识点 · {categories.length} 个领域
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {!hasMastery ? (
          <div className="text-center text-muted-foreground py-8 text-sm">
            暂无掌握度数据，完成练习后将更新 BKT 模型
          </div>
        ) : (
          <div className="space-y-4">
            <div className="relative rounded-xl border border-border/30 bg-gradient-to-br from-[hsl(30_25%_98%)] via-[hsl(30_20%_97%)] to-[hsl(30_25%_96%)] overflow-hidden">
              <svg
                viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
                className="w-full h-auto"
                style={{ maxHeight: 340 }}
              >
                <defs>
                  <radialGradient id="center-grad" cx="50%" cy="50%" r="50%">
                    <stop offset="0%" stopColor="hsl(160 25% 85%)" stopOpacity="0.3" />
                    <stop offset="100%" stopColor="hsl(160 25% 95%)" stopOpacity="0" />
                  </radialGradient>
                  <filter id="soft-shadow" x="-50%" y="-50%" width="200%" height="200%">
                    <feDropShadow dx="0" dy="1" stdDeviation="2" floodColor="hsl(25 15% 18%)" floodOpacity="0.08" />
                  </filter>
                </defs>

                <ellipse cx={CX} cy={CY} rx="180" ry="130" fill="url(#center-grad)" />

                {bgDots.map((d, i) => (
                  <circle key={i} cx={d.x} cy={d.y} r={d.r} fill="hsl(25 10% 70%)" opacity={d.o} />
                ))}

                <circle cx={CX} cy={CY} r={70} fill="none" stroke="hsl(30 12% 86%)" strokeWidth="0.5" strokeOpacity="0.6" />
                <circle cx={CX} cy={CY} r={140} fill="none" stroke="hsl(30 12% 86%)" strokeWidth="0.5" strokeOpacity="0.4" />

                {categoryStats.map((cat, idx) => {
                  const angle = (idx * (2 * Math.PI)) / categories.length - Math.PI / 2;
                  const lx = CX + Math.cos(angle) * 175;
                  const ly = CY + Math.sin(angle) * 175;
                  return (
                    <g key={cat.key}>
                      <line
                        x1={CX}
                        y1={CY}
                        x2={lx}
                        y2={ly}
                        stroke={cat.color}
                        strokeWidth="0.5"
                        strokeOpacity="0.25"
                        strokeDasharray="4 3"
                      />
                      <text
                        x={lx}
                        y={ly}
                        textAnchor="middle"
                        dominantBaseline="middle"
                        fill={cat.color}
                        fillOpacity="0.85"
                        fontSize="11"
                        fontWeight="500"
                        style={{ fontFamily: "var(--font-sans)" }}
                      >
                        {cat.label}
                      </text>
                    </g>
                  );
                })}

                {layout.edges.map(([a, b], i) => {
                  const na = layout.nodes[a];
                  const nb = layout.nodes[b];
                  const edgeOpacity = Math.min(na.value, nb.value) * 0.25 + 0.05;
                  return (
                    <line
                      key={i}
                      x1={na.x}
                      y1={na.y}
                      x2={nb.x}
                      y2={nb.y}
                      stroke="hsl(25 10% 50%)"
                      strokeWidth="0.4"
                      strokeOpacity={edgeOpacity}
                      strokeDasharray="2 2"
                    />
                  );
                })}

                {layout.nodes.map((node) => (
                  <g
                    key={node.id}
                    onMouseEnter={() => setHovered(node)}
                    onMouseLeave={() => setHovered(null)}
                    style={{ cursor: "pointer" }}
                  >
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={node.r + 4}
                      fill={getNodeBg(node.value)}
                      opacity={hovered?.id === node.id ? 0.9 : 0.5}
                      style={{ transition: "opacity 0.2s ease" }}
                    />
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={node.r}
                      fill={getNodeFill(node.value)}
                      opacity={hovered?.id === node.id ? 1 : 0.75}
                      stroke={getNodeStroke(node.value)}
                      strokeWidth={hovered?.id === node.id ? 1.5 : 1}
                      strokeOpacity="0.7"
                      filter="url(#soft-shadow)"
                      style={{ transition: "all 0.2s ease" }}
                    />
                    {node.value >= 0.8 && (
                      <circle
                        cx={node.x}
                        cy={node.y}
                        r={node.r + 2}
                        fill="none"
                        stroke={getNodeStroke(node.value)}
                        strokeWidth="0.6"
                        strokeOpacity="0.45"
                        strokeDasharray="2 1"
                      />
                    )}
                  </g>
                ))}

                {hovered && (
                  <g>
                    <rect
                      x={Math.min(hovered.x + 12, VIEW_W - 145)}
                      y={Math.max(hovered.y - 34, 6)}
                      width="135"
                      height="52"
                      rx="8"
                      fill="hsl(0 0% 100%)"
                      stroke={hovered.category.color}
                      strokeWidth="0.6"
                      strokeOpacity="0.4"
                      filter="url(#soft-shadow)"
                    />
                    <rect
                      x={Math.min(hovered.x + 12, VIEW_W - 145)}
                      y={Math.max(hovered.y - 34, 6)}
                      width="135"
                      height="52"
                      rx="8"
                      fill={hovered.category.color}
                      fillOpacity="0.04"
                    />
                    <text
                      x={Math.min(hovered.x + 20, VIEW_W - 137)}
                      y={Math.max(hovered.y - 18, 22)}
                      fill="hsl(25 15% 18%)"
                      fontSize="10"
                      fontWeight="600"
                      style={{ fontFamily: "var(--font-sans)" }}
                    >
                      {hovered.label.length > 18 ? hovered.label.slice(0, 18) + "…" : hovered.label}
                    </text>
                    <text
                      x={Math.min(hovered.x + 20, VIEW_W - 137)}
                      y={Math.max(hovered.y - 2, 38)}
                      fill={getNodeFill(hovered.value)}
                      fontSize="12"
                      fontWeight="700"
                      style={{ fontFamily: "var(--font-sans)" }}
                    >
                      掌握度 {(hovered.value * 100).toFixed(0)}%
                    </text>
                    <text
                      x={Math.min(hovered.x + 20, VIEW_W - 137)}
                      y={Math.max(hovered.y + 12, 52)}
                      fill="hsl(25 5% 50%)"
                      fontSize="9"
                      style={{ fontFamily: "var(--font-sans)" }}
                    >
                      {hovered.category.label}
                    </text>
                  </g>
                )}
              </svg>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {categoryStats.map((cat) => (
                <div
                  key={cat.key}
                  className={cn(
                    "rounded-lg border border-border/40 bg-secondary/30 p-2.5 transition-all",
                    cat.count === 0 && "opacity-40"
                  )}
                >
                  <div className="flex items-center gap-1.5 mb-1">
                    <span
                      className="h-2 w-2 rounded-full flex-shrink-0"
                      style={{ backgroundColor: cat.color }}
                    />
                    <span className="text-xs font-medium truncate text-foreground/80">{cat.label}</span>
                  </div>
                  <div className="flex items-baseline gap-1.5">
                    <span
                      className="text-lg font-bold"
                      style={{ color: cat.color }}
                    >
                      {(cat.avg * 100).toFixed(0)}%
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      / {cat.count} 个
                    </span>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex items-center justify-center gap-3 text-[10px] text-muted-foreground pt-1">
              <span className="flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: "#c47a7a" }} />
                薄弱 ({'<'}35%)
              </span>
              <span className="flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: "#d4a574" }} />
                一般 (35-60%)
              </span>
              <span className="flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: "#7ba696" }} />
                良好 (60-85%)
              </span>
              <span className="flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: "#4a8c74" }} />
                精通 (≥85%)
              </span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}