import { useMemo, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PieChart } from "lucide-react";
import { SUNBURST_TREE, type SunburstTreeNode } from "./sunburst-tree";
import { buildChapterGroups, computeMasteryStats } from "@/lib/knowledge-map";

interface MasterySunburstProps {
  mastery?: Record<string, number>;
}

interface Segment {
  node: SunburstTreeNode;
  start: number;
  end: number;
  depth: number;
  pl: number;
  color: string;
  path: string[];
}

interface HoverState {
  name: string;
  path: string;
  pathArr: string[];
  pl: number;
  color: string;
  x: number;
  y: number;
}

/** 判断 segPath 是否为 hoverPath 的祖先或本身，用于 emphasis focus="ancestor" 效果 */
function isAncestorOrSelf(segPath: string[], hoverPath: string[]): boolean {
  if (segPath.length > hoverPath.length) return false;
  return segPath.every((v, i) => v === hoverPath[i]);
}

const SIZE = 640;
const CX = SIZE / 2;
const CY = SIZE / 2;
const R_INNER = SIZE * 0.5 * 0.12;
const R_OUTER = SIZE * 0.5 * 0.92;
const DEFAULT_PL = 0.15;

/** 各顶层章节的基础色相：每个章节一种颜色，章节内用深浅表示掌握度。 */
const BRANCH_HUES: Record<string, number> = {
  "patent-law-foundation": 145, // 绿
  "patentability-substantive": 45, // 琥珀
  "patent-application-process": 5, // 红
  "patent-examination": 205, // 蓝
  "patent-reexamination": 168, // 青绿
  "patent-invalidation": 26, // 橙
  "patent-rights-protection": 270, // 紫
  "patent-agency-practice": 322, // 品红
  "related-laws": 232, // 靛蓝
  "pct-system": 187, // 青
};

/** P(L) → 颜色：色相由所属章节决定，饱和度/深浅反映掌握度（低掌握浅、高掌握深）。 */
function plToColor(pl: number, hue: number): string {
  const clamped = Math.max(0.1, Math.min(1.0, pl));
  const t = (clamped - 0.1) / 0.9;
  const saturation = 30 + t * 52;
  const lightness = 86 - t * 54;
  return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
}

/** 章节的色相：优先取色板，未收录的章节用黄金角取色兜底，保证任意章节都有独立颜色。 */
function branchHue(node: SunburstTreeNode, index: number): number {
  return BRANCH_HUES[node.englishId] ?? (index * 137.5) % 360;
}

function polar(r: number, angle: number): [number, number] {
  return [CX + r * Math.sin(angle), CY - r * Math.cos(angle)];
}

function arcPath(r0: number, r1: number, a0: number, a1: number): string {
  const [x0, y0] = polar(r1, a0);
  const [x1, y1] = polar(r1, a1);
  const [x2, y2] = polar(r0, a1);
  const [x3, y3] = polar(r0, a0);
  const largeArc = a1 - a0 > Math.PI ? 1 : 0;
  return `M ${x0} ${y0} A ${r1} ${r1} 0 ${largeArc} 1 ${x1} ${y1} L ${x2} ${y2} A ${r0} ${r0} 0 ${largeArc} 0 ${x3} ${y3} Z`;
}

function labelTransform(r: number, angle: number): string {
  const [x, y] = polar(r, angle);
  // 径向（radial）方向：与参考 ECharts sunburst 的 rotate: "radial" 一致，
  // 文字沿半径由内向外排列；下半圆翻转 180° 避免倒置。
  let deg = (angle * 180) / Math.PI - 90;
  deg = ((deg % 360) + 360) % 360;
  if (deg > 90 && deg < 270) deg += 180;
  return `translate(${x},${y}) rotate(${deg})`;
}

/** 径向标签沿半径延伸，可用长度受环宽限制，超长时截断（完整名见悬浮提示）。 */
function truncateLabel(name: string, depth: number): string {
  const max = depth === 1 ? 12 : depth === 2 ? 9 : 7;
  return name.length > max ? `${name.slice(0, max)}…` : name;
}

function nodeValue(node: SunburstTreeNode): number {
  if (!node.children || node.children.length === 0) return node.value ?? 1;
  return node.children.reduce((sum, c) => sum + nodeValue(c), 0);
}

/** 与参考实现一致：优先取该节点自身的 P(L)，否则取后代叶子均值，最后回退 0.15。 */
function computePl(
  node: SunburstTreeNode,
  plMap: Record<string, number>
): { pl: number; leafPls: number[] } {
  let leafPls: number[] = [];
  if (node.children) {
    for (const child of node.children) {
      leafPls = leafPls.concat(computePl(child, plMap).leafPls);
    }
  }
  const direct = plMap[node.englishId];
  let pl: number;
  if (typeof direct === "number" && !Number.isNaN(direct)) {
    pl = direct;
  } else if (leafPls.length > 0) {
    pl = leafPls.reduce((a, b) => a + b, 0) / leafPls.length;
  } else {
    pl = DEFAULT_PL;
  }
  const isLeaf = !node.children || node.children.length === 0;
  return { pl, leafPls: isLeaf ? [pl] : leafPls };
}

export function MasterySunburst({ mastery }: MasterySunburstProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [hovered, setHovered] = useState<HoverState | null>(null);

  const plMap = useMemo(() => mastery || {}, [mastery]);

  const { segments, maxDepth, overallAvg } = useMemo(() => {
    const segs: Segment[] = [];
    let depth = 1;

    function measure(node: SunburstTreeNode, d: number) {
      depth = Math.max(depth, d);
      node.children?.forEach((c) => measure(c, d + 1));
    }
    SUNBURST_TREE.forEach((n) => measure(n, 1));

    function layout(
      node: SunburstTreeNode,
      start: number,
      span: number,
      d: number,
      path: string[],
      hue: number
    ) {
      const { pl } = computePl(node, plMap);
      segs.push({
        node,
        start,
        end: start + span,
        depth: d,
        pl,
        color: plToColor(pl, hue),
        path,
      });
      if (node.children && node.children.length > 0) {
        const total = node.children.reduce((s, c) => s + nodeValue(c), 0);
        let a = start;
        for (const child of node.children) {
          const w = total > 0 ? (nodeValue(child) / total) * span : 0;
          layout(child, a, w, d + 1, [...path, child.name], hue);
          a += w;
        }
      }
    }

    const totalValue = SUNBURST_TREE.reduce((s, n) => s + nodeValue(n), 0);
    let angle = 0;
    SUNBURST_TREE.forEach((top, i) => {
      const span = totalValue > 0 ? (nodeValue(top) / totalValue) * Math.PI * 2 : 0;
      layout(top, angle, span, 1, [top.name], branchHue(top, i));
      angle += span;
    });

    // 与 BlindSpotGraph 共用同一统计口径，保证中心"综合掌握度"与盲区定位图的"平均掌握度"数值一致。
    const stats = computeMasteryStats(
      buildChapterGroups(SUNBURST_TREE),
      plMap as unknown as Record<string, unknown>,
    );

    return { segments: segs, maxDepth: depth, overallAvg: stats.avgMastery };
  }, [plMap]);

  const ringOf = (depth: number): [number, number] => {
    const r0 = R_INNER + ((R_OUTER - R_INNER) * (depth - 1)) / maxDepth;
    const r1 = R_INNER + ((R_OUTER - R_INNER) * depth) / maxDepth;
    return [r0, r1];
  };

  const minAngleFor = (depth: number): number => {
    if (depth === 1) return 0.14;
    if (depth === 2) return 0.09;
    return 0.055;
  };

  const labelColor = (pl: number): string => {
    const t = (Math.max(0.1, Math.min(1.0, pl)) - 0.1) / 0.9;
    return t > 0.55 ? "#ffffff" : "#3a4a5c";
  };

  const handleMove = (e: React.MouseEvent) => {
    const rect = wrapRef.current?.getBoundingClientRect();
    if (!rect) return;
    setHovered((prev) =>
      prev
        ? {
            ...prev,
            x: Math.min(e.clientX - rect.left + 14, rect.width - 200),
            y: Math.min(e.clientY - rect.top + 14, rect.height - 90),
          }
        : prev
    );
  };

  return (
    <Card className="rounded-2xl border border-white/70 bg-white/90 shadow-soft overflow-hidden h-full">
      <div className="h-1.5 w-full bg-gradient-to-r from-[#D9773E] via-[#F59E0B] to-[#C15B27]" />
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-medium flex items-center gap-2 text-[#5C3A26]">
          <span className="inline-flex items-center justify-center rounded-lg bg-[#D9773E]/10 p-1.5 text-[#D9773E]">
            <PieChart className="h-4 w-4" />
          </span>
          知识掌握度旭日图
          <span className="text-xs text-muted-foreground font-normal">
            · 每章节一种颜色 · 章节内颜色深浅反映 P(L) 掌握度
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col items-center gap-3">
          <div
            ref={wrapRef}
            className="relative w-full max-w-[620px]"
            onMouseMove={handleMove}
          >
            <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="w-full h-auto">
              <defs>
                <filter id="seg-hover-shadow" x="-20%" y="-20%" width="140%" height="140%">
                  <feDropShadow dx="0" dy="2" stdDeviation="4" floodColor="rgba(0,0,0,0.25)" />
                </filter>
              </defs>
              {/* 中心信息 */}
              <circle cx={CX} cy={CY} r={R_INNER - 2} fill="#fff" />
              <text x={CX} y={CY - 4} textAnchor="middle" fontSize="12" fill="#7f8c99">
                综合掌握度
              </text>
              <text
                x={CX}
                y={CY + 16}
                textAnchor="middle"
                fontSize="20"
                fontWeight="700"
                fill="#C15B27"
              >
                {(overallAvg * 100).toFixed(0)}%
              </text>

              {segments.map((seg) => {
                const [r0, r1] = ringOf(seg.depth);
                const span = seg.end - seg.start;
                const mid = (seg.start + seg.end) / 2;
                const showLabel = span >= minAngleFor(seg.depth);
                const active = hovered ? isAncestorOrSelf(seg.path, hovered.pathArr) : false;
                const isSelf = hovered
                  ? active && seg.path.length === hovered.pathArr.length
                  : false;
                return (
                  <g
                    key={`${seg.path.join("/")}-${seg.start.toFixed(4)}`}
                    onMouseEnter={(e) => {
                      const rect = wrapRef.current?.getBoundingClientRect();
                      setHovered({
                        name: seg.node.name,
                        path: seg.path.join(" → "),
                        pathArr: seg.path,
                        pl: seg.pl,
                        color: seg.color,
                        x: rect ? e.clientX - rect.left + 14 : 0,
                        y: rect ? e.clientY - rect.top + 14 : 0,
                      });
                    }}
                    onMouseLeave={() => setHovered(null)}
                    opacity={hovered ? (active ? 1 : 0.12) : 1}
                    style={{ cursor: "pointer", transition: "opacity 0.2s ease" }}
                  >
                    <path
                      d={arcPath(r0, r1, seg.start, seg.end)}
                      fill={seg.color}
                      stroke={isSelf ? "#ffffff" : "rgba(255,255,255,0.7)"}
                      strokeWidth={isSelf ? 2.5 : seg.depth === 1 ? 2 : 1}
                      filter={isSelf ? "url(#seg-hover-shadow)" : undefined}
                    />
                    {showLabel && (
                      <text
                        transform={labelTransform((r0 + r1) / 2, mid)}
                        textAnchor="middle"
                        dominantBaseline="middle"
                        fontSize={seg.depth === 1 ? 12 : seg.depth === 2 ? 10 : 8}
                        fontWeight={seg.depth === 1 ? 700 : 500}
                        fill={labelColor(seg.pl)}
                      >
                        {truncateLabel(seg.node.name, seg.depth)}
                      </text>
                    )}
                  </g>
                );
              })}
            </svg>

            {hovered && (
              <div
                className="absolute pointer-events-none z-10 rounded-lg px-3 py-2 text-xs text-white shadow-lg"
                style={{
                  left: hovered.x,
                  top: hovered.y,
                  background: "rgba(30,40,55,0.94)",
                  border: "1px solid rgba(255,255,255,0.15)",
                  maxWidth: 240,
                }}
              >
                <div className="font-bold text-[13px] mb-0.5">{hovered.name}</div>
                <div className="opacity-75 mb-1">路径：{hovered.path}</div>
                <div className="flex items-center gap-1.5 border-t border-white/20 pt-1">
                  <span
                    className="inline-block h-2.5 w-2.5 rounded-full"
                    style={{ background: hovered.color }}
                  />
                  <span>
                    <strong>P(L)：</strong>
                    {hovered.pl.toFixed(4)}
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* 章节颜色图例：与图中一致，每章节一种颜色，条内浅→深=低→高掌握 */}
          <div className="w-full space-y-2">
            <div className="flex items-center justify-center gap-1.5 text-[11px] text-muted-foreground">
              <span>同一章节内：</span>
              <span>浅色=低掌握（0.15）</span>
              <span aria-hidden>→</span>
              <span className="font-semibold text-[#3a4a5c]">深色=高掌握（≈1.0）</span>
            </div>
            <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1.5">
              {SUNBURST_TREE.map((top, i) => {
                const hue = branchHue(top, i);
                return (
                  <div key={top.englishId} className="flex items-center gap-1.5">
                    <div
                      className="h-2.5 w-14 rounded-full"
                      style={{
                        background: `linear-gradient(90deg, ${plToColor(0.15, hue)} 0%, ${plToColor(1, hue)} 100%)`,
                      }}
                    />
                    <span className="text-[11px] text-muted-foreground">{top.name}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
