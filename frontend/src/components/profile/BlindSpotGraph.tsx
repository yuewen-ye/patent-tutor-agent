import { useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import {
  AlertTriangle,
  GraduationCap,
  BookOpen,
  HelpCircle,
  ZoomIn,
  TrendingUp,
  ChevronDown,
  ChevronRight,
  ChevronsDown,
  ChevronsUp,
  Minimize2,
  Maximize2,
} from "lucide-react";
import type { ConfusionAxisItem } from "@/types";
import {
  buildChapterGroups,
  classifyMastery,
  computeMasteryStats,
  extractPl,
  masteryStateColor,
  nodeIdToName,
  type ChapterGroup,
  type KnowledgeState,
} from "@/lib/knowledge-map";

interface BlindSpotGraphProps {
  masterySnapshot?: Record<string, unknown> | null;
  weakPoints?: string[] | null;
  confusionAxis?: ConfusionAxisItem[] | null;
  className?: string;
}

type NodeColorStyles = {
  card: string;
  dot: string;
  ring: string;
  text: string;
  percent: string;
};

function getNodeStyles(state: KnowledgeState): NodeColorStyles {
  switch (state) {
    case "blind_spot":
      return {
        card: "bg-rose-50 border-rose-300/70 hover:bg-rose-100 hover:border-rose-400",
        dot: "bg-rose-500",
        ring: "ring-rose-200",
        text: "text-rose-900",
        percent: "text-rose-700",
      };
    case "learning":
      return {
        card: "bg-amber-50 border-amber-300/70 hover:bg-amber-100 hover:border-amber-400",
        dot: "bg-amber-500",
        ring: "ring-amber-200",
        text: "text-amber-900",
        percent: "text-amber-700",
      };
    case "mastered":
      return {
        card: "bg-emerald-50 border-emerald-300/70 hover:bg-emerald-100 hover:border-emerald-400",
        dot: "bg-emerald-500",
        ring: "ring-emerald-200",
        text: "text-emerald-900",
        percent: "text-emerald-700",
      };
    default:
      return {
        card: "bg-slate-50 border-slate-200 hover:bg-slate-100 hover:border-slate-300",
        dot: "bg-slate-400",
        ring: "ring-slate-200",
        text: "text-slate-700",
        percent: "text-slate-500",
      };
  }
}

function stateLabel(state: KnowledgeState): string {
  switch (state) {
    case "blind_spot":
      return "知识盲区";
    case "learning":
      return "学习中";
    case "mastered":
      return "已掌握";
    default:
      return "未评估";
  }
}

export function BlindSpotGraph({
  masterySnapshot,
  weakPoints,
  confusionAxis,
  className,
}: BlindSpotGraphProps) {
  const groups: ChapterGroup[] = useMemo(() => buildChapterGroups(), []);
  const stats = useMemo(
    () => computeMasteryStats(groups, masterySnapshot ?? undefined),
    [groups, masterySnapshot],
  );

  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [showOnlyBlind, setShowOnlyBlind] = useState(false);
  // 整体折叠：true=只显示顶部概要（标题+统计卡+图例），隐藏章节网格
  const [overallCollapsed, setOverallCollapsed] = useState(false);

  // 计算每个章节是否包含盲区节点，用于默认展开策略
  const chapterHasBlindSpot = useMemo(() => {
    const res: Record<string, boolean> = {};
    for (const g of groups) {
      let has = false;
      for (const n of g.nodes) {
        const pl = extractPl(masterySnapshot?.[n.nodeId]);
        if (classifyMastery(pl).state === "blind_spot") {
          has = true;
          break;
        }
      }
      res[g.chapterId] = has;
    }
    return res;
  }, [groups, masterySnapshot]);

  // 各章节折叠状态：默认仅展开有盲区的章节，其余折叠
  const [collapsedChapters, setCollapsedChapters] = useState<Record<string, boolean>>(() => {
    const init: Record<string, boolean> = {};
    for (const g of groups) {
      init[g.chapterId] = !chapterHasBlindSpot[g.chapterId]; // 无盲区 → 折叠
    }
    return init;
  });

  const weakPointSet = useMemo(
    () => new Set((weakPoints ?? []).map((w) => w.trim().toLowerCase())),
    [weakPoints],
  );
  const confusionByNode = useMemo(() => {
    const map = new Map<string, ConfusionAxisItem[]>();
    for (const item of confusionAxis ?? []) {
      if (!item.is_active) continue;
      for (const nid of item.pair_id.split(/[-_]/)) {
        const arr = map.get(nid) ?? [];
        arr.push(item);
        map.set(nid, arr);
      }
      const pairLower = item.title.toLowerCase();
      for (const group of groups) {
        for (const node of group.nodes) {
          if (
            pairLower.includes(node.nodeName.toLowerCase()) ||
            pairLower.includes(node.nodeId.toLowerCase())
          ) {
            const arr = map.get(node.nodeId) ?? [];
            if (!arr.includes(item)) arr.push(item);
            map.set(node.nodeId, arr);
          }
        }
      }
    }
    return map;
  }, [confusionAxis, groups]);

  // 统计每个章节的各状态节点数，折叠时显示概览
  const chapterStats = useMemo(() => {
    const map: Record<
      string,
      { blindSpot: number; learning: number; mastered: number; unknown: number }
    > = {};
    for (const g of groups) {
      let bs = 0,
        ln = 0,
        ms = 0,
        un = 0;
      for (const n of g.nodes) {
        const s = classifyMastery(extractPl(masterySnapshot?.[n.nodeId])).state;
        if (s === "blind_spot") bs += 1;
        else if (s === "learning") ln += 1;
        else if (s === "mastered") ms += 1;
        else un += 1;
      }
      map[g.chapterId] = { blindSpot: bs, learning: ln, mastered: ms, unknown: un };
    }
    return map;
  }, [groups, masterySnapshot]);

  const selectedStatus = useMemo(() => {
    if (!selectedNode) return null;
    const raw = masterySnapshot?.[selectedNode];
    const pl = extractPl(raw);
    return {
      ...classifyMastery(pl),
      hasWeak:
        weakPointSet.has(selectedNode.toLowerCase()) ||
        weakPointSet.has(nodeIdToName(selectedNode).toLowerCase()),
      confusions: confusionByNode.get(selectedNode) ?? [],
    };
  }, [selectedNode, masterySnapshot, weakPointSet, confusionByNode]);

  const chaptersToShow = useMemo(() => {
    if (!showOnlyBlind) return groups;
    return groups
      .map((g) => {
        const filteredNodes = g.nodes.filter((n) => {
          const raw = masterySnapshot?.[n.nodeId];
          const pl = extractPl(raw);
          return classifyMastery(pl).state === "blind_spot";
        });
        return { ...g, nodes: filteredNodes };
      })
      .filter((g) => g.nodes.length > 0);
  }, [groups, showOnlyBlind, masterySnapshot]);

  const toggleChapter = (chapterId: string) => {
    setCollapsedChapters((prev) => ({ ...prev, [chapterId]: !prev[chapterId] }));
  };

  const expandAllChapters = () => {
    const next: Record<string, boolean> = {};
    for (const g of chaptersToShow) next[g.chapterId] = false;
    setCollapsedChapters(next);
  };

  const collapseAllChapters = () => {
    const next: Record<string, boolean> = {};
    for (const g of chaptersToShow) next[g.chapterId] = true;
    setCollapsedChapters(next);
  };

  return (
    <>
      <Card className={`border-border/40 bg-card shadow-soft ${className ?? ""}`}>
        <CardHeader className="pb-3">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
            <div>
              <CardTitle className="text-base font-medium flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-rose-500" />
                知识盲区定位图
              </CardTitle>
              <p className="text-xs text-muted-foreground mt-1">
                基于 BKT 掌握概率 P(L) 对每个知识点进行三态分类。点击节点查看盲区归因与混淆关联。
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => setShowOnlyBlind((v) => !v)}
                className={`text-xs px-2.5 py-1.5 rounded-md border transition-colors ${
                  showOnlyBlind
                    ? "bg-rose-100 text-rose-700 border-rose-300"
                    : "bg-white text-foreground border-border/60 hover:bg-secondary/30"
                }`}
              >
                {showOnlyBlind ? "显示全部" : "只看盲区"}
              </button>
              <button
                type="button"
                onClick={() => setOverallCollapsed((v) => !v)}
                className="text-xs px-2.5 py-1.5 rounded-md border border-border/60 bg-white text-foreground hover:bg-secondary/30 transition-colors flex items-center gap-1.5"
                title={overallCollapsed ? "展开详情" : "折叠详情"}
              >
                {overallCollapsed ? (
                  <>
                    <Maximize2 className="h-3 w-3" /> 展开
                  </>
                ) : (
                  <>
                    <Minimize2 className="h-3 w-3" /> 折叠
                  </>
                )}
              </button>
            </div>
          </div>

          {/* 三态统计 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3">
            <StatCard
              icon={<AlertTriangle className="h-3.5 w-3.5 text-rose-500" />}
              label="知识盲区"
              value={`${stats.blindSpotCount}`}
              sub={`${Math.round(stats.blindSpotRate * 100)}% 节点`}
              cardClass="bg-rose-50 border-rose-200/60"
              valueClass="text-rose-700"
            />
            <StatCard
              icon={<TrendingUp className="h-3.5 w-3.5 text-amber-500" />}
              label="学习中"
              value={`${stats.learningCount}`}
              sub="0.4 ≤ P(L) < 0.8"
              cardClass="bg-amber-50 border-amber-200/60"
              valueClass="text-amber-700"
            />
            <StatCard
              icon={<GraduationCap className="h-3.5 w-3.5 text-emerald-500" />}
              label="已掌握"
              value={`${stats.masteredCount}`}
              sub="P(L) ≥ 0.8"
              cardClass="bg-emerald-50 border-emerald-200/60"
              valueClass="text-emerald-700"
            />
            <StatCard
              icon={<BookOpen className="h-3.5 w-3.5 text-primary" />}
              label="平均掌握度"
              value={`${Math.round(stats.avgMastery * 100)}%`}
              sub={`共 ${stats.totalCount} 节点`}
              cardClass="bg-[#FFF7ED] border-[#E5C9AB]/70"
              valueClass="text-[#C15B27]"
            />
          </div>

          {/* 图例 */}
          <div className="flex flex-wrap items-center gap-3 mt-3 pt-3 border-t border-border/40">
            <LegendSwatch dotClass="bg-rose-500" label="盲区 P(L)<0.4" />
            <LegendSwatch dotClass="bg-amber-500" label="学习中 0.4≤P(L)<0.8" />
            <LegendSwatch dotClass="bg-emerald-500" label="掌握 P(L)≥0.8" />
            <LegendSwatch dotClass="bg-slate-400" label="未评估" />
          </div>
        </CardHeader>

        {!overallCollapsed && (
          <CardContent className="space-y-4">
            {chaptersToShow.length === 0 ? (
              <div className="py-10 text-center text-sm text-muted-foreground">
                {showOnlyBlind ? "当前没有识别到的知识盲区 🎉" : "暂无掌握度数据"}
              </div>
            ) : (
              <>
                {/* 章节批量操作条 */}
                <div className="flex items-center justify-between gap-2 pb-1">
                  <span className="text-[11px] text-muted-foreground tracking-wide">
                    共 {chaptersToShow.length} 个章节 · 默认仅展开含盲区的章节
                  </span>
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={expandAllChapters}
                      className="text-[11px] px-2 py-1 rounded border border-border/60 text-muted-foreground hover:bg-secondary/30 hover:text-foreground transition-colors flex items-center gap-1"
                      title="展开全部章节"
                    >
                      <ChevronsDown className="h-3 w-3" />
                      全部展开
                    </button>
                    <button
                      type="button"
                      onClick={collapseAllChapters}
                      className="text-[11px] px-2 py-1 rounded border border-border/60 text-muted-foreground hover:bg-secondary/30 hover:text-foreground transition-colors flex items-center gap-1"
                      title="折叠全部章节"
                    >
                      <ChevronsUp className="h-3 w-3" />
                      全部折叠
                    </button>
                  </div>
                </div>

                {chaptersToShow.map((group) => {
                  const collapsed = collapsedChapters[group.chapterId] ?? false;
                  const cs = chapterStats[group.chapterId] ?? {
                    blindSpot: 0,
                    learning: 0,
                    mastered: 0,
                    unknown: 0,
                  };
                  return (
                    <div
                      key={group.chapterId}
                      className={`rounded-lg border transition-colors ${
                        collapsed
                          ? "border-border/30 bg-secondary/10"
                          : "border-border/40 bg-card"
                      }`}
                    >
                      {/* 章节头：可点击折叠 / 展开 */}
                      <button
                        type="button"
                        onClick={() => toggleChapter(group.chapterId)}
                        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-secondary/20 transition-colors rounded-lg text-left"
                      >
                        {collapsed ? (
                          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/70 flex-shrink-0" />
                        ) : (
                          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground/70 flex-shrink-0" />
                        )}
                        <span className="text-xs font-medium tracking-wide text-[#5C3A26]">
                          {group.chapterName}
                        </span>
                        <span className="text-[10px] text-muted-foreground font-normal">
                          · {group.nodes.length} 节点
                        </span>
                        {/* 折叠时章节头内联三态计数，提供概览 */}
                        <div className="flex items-center gap-2 ml-auto">
                          {collapsed && (
                            <>
                              <ChapterCountDot colorClass="bg-rose-500" count={cs.blindSpot} />
                              <ChapterCountDot colorClass="bg-amber-500" count={cs.learning} />
                              <ChapterCountDot colorClass="bg-emerald-500" count={cs.mastered} />
                              {cs.unknown > 0 && (
                                <ChapterCountDot colorClass="bg-slate-400" count={cs.unknown} />
                              )}
                            </>
                          )}
                          {!collapsed && cs.blindSpot > 0 && (
                            <Badge
                              variant="outline"
                              className="h-5 text-[10px] px-1.5 bg-rose-100/70 text-rose-700 border-rose-300"
                            >
                              {cs.blindSpot} 盲区
                            </Badge>
                          )}
                        </div>
                      </button>

                      {/* 章节节点网格 */}
                      {!collapsed && (
                        <div className="px-3 pb-3 pt-1">
                          <div className="flex flex-wrap gap-2">
                            {group.nodes.map((node) => {
                              const raw = masterySnapshot?.[node.nodeId];
                              const pl = extractPl(raw);
                              const { state } = classifyMastery(pl);
                              const styles = getNodeStyles(state);
                              const pct = Math.round((pl ?? 0) * 100);
                              return (
                                <button
                                  key={node.nodeId}
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setSelectedNode(node.nodeId);
                                  }}
                                  className={`group relative px-3 py-2 rounded-lg border transition-all duration-150 text-left max-w-[168px] focus:outline-none focus:ring-2 ${styles.ring} ${styles.card}`}
                                >
                                  <div className="flex items-start gap-2">
                                    <span
                                      className={`inline-block h-1.5 w-1.5 rounded-full mt-1.5 flex-shrink-0 ${styles.dot}`}
                                    />
                                    <div className="min-w-0 flex-1">
                                      <div
                                        className={`text-[12px] font-normal tracking-wide leading-snug line-clamp-2 ${styles.text}`}
                                      >
                                        {node.nodeName}
                                      </div>
                                      <div
                                        className={`text-[10px] mt-0.5 font-medium ${styles.percent}`}
                                      >
                                        {pl === undefined ? "未评估" : `P(L) ${pct}%`}
                                      </div>
                                    </div>
                                    <ZoomIn className="h-3 w-3 text-muted-foreground/30 group-hover:text-muted-foreground/70 transition-opacity mt-1 flex-shrink-0" />
                                  </div>
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </>
            )}
          </CardContent>
        )}
      </Card>

      {/* 节点详情弹窗 */}
      <Dialog open={selectedNode !== null} onOpenChange={(o) => !o && setSelectedNode(null)}>
        <DialogContent className="max-w-lg">
          {selectedNode && selectedStatus && (
            <>
              <DialogHeader>
                <DialogTitle className="text-lg">{nodeIdToName(selectedNode)}</DialogTitle>
                <DialogDescription className="font-mono text-[11px] text-muted-foreground/80">
                  node_id: {selectedNode}
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-4 pt-2">
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-medium text-muted-foreground">掌握状态</span>
                    <span
                      className={`text-xs font-semibold ${masteryStateColor(selectedStatus.state)}`}
                    >
                      {stateLabel(selectedStatus.state)}
                    </span>
                  </div>
                  <Progress value={Math.round(selectedStatus.pl * 100)} className="h-2.5" />
                  <div className="flex justify-between text-[10px] text-muted-foreground mt-1">
                    <span>盲区阈值 40%</span>
                    <span className="font-medium text-foreground/80">
                      P(L) = {Math.round(selectedStatus.pl * 100)}%
                    </span>
                    <span>掌握阈值 80%</span>
                  </div>
                </div>

                <div>
                  <div className="text-xs font-medium text-muted-foreground mb-1.5">
                    诊断薄弱点标记
                  </div>
                  {selectedStatus.hasWeak ? (
                    <Badge variant="destructive" className="text-[11px]">
                      <AlertTriangle className="h-3 w-3 mr-1" />
                      诊断 Agent 标记为薄弱点
                    </Badge>
                  ) : (
                    <span className="text-xs text-muted-foreground">未被标记为薄弱点</span>
                  )}
                </div>

                <div>
                  <div className="text-xs font-medium text-muted-foreground mb-1.5">
                    关联激活混淆对（{selectedStatus.confusions.length}）
                  </div>
                  {selectedStatus.confusions.length === 0 ? (
                    <span className="text-xs text-muted-foreground">暂无激活的混淆关联</span>
                  ) : (
                    <div className="space-y-2">
                      {selectedStatus.confusions.slice(0, 3).map((c) => (
                        <div
                          key={c.pair_id}
                          className="rounded-md border border-amber-200/70 bg-amber-50/70 p-2.5"
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-medium">{c.title}</span>
                            <Badge
                              variant="outline"
                              className="text-[10px] bg-amber-100/70 text-amber-700 border-amber-300"
                            >
                              风险 {Math.round(c.learner_risk * 100)}%
                            </Badge>
                          </div>
                          <p className="text-[11px] text-muted-foreground leading-relaxed">
                            {c.adjustment_reason}
                          </p>
                        </div>
                      ))}
                      {selectedStatus.confusions.length > 3 && (
                        <p className="text-[10px] text-muted-foreground text-center">
                          另有 {selectedStatus.confusions.length - 3} 条关联混淆对
                        </p>
                      )}
                    </div>
                  )}
                </div>

                {selectedStatus.state === "blind_spot" && (
                  <div className="rounded-md border border-rose-200/70 bg-rose-50/60 p-3">
                    <div className="flex items-center gap-1.5 mb-1.5">
                      <HelpCircle className="h-3.5 w-3.5 text-rose-600" />
                      <span className="text-xs font-semibold text-rose-700">盲区归因建议</span>
                    </div>
                    <p className="text-[11px] text-rose-800/85 leading-relaxed">
                      该知识点 P(L) 低于 40%，建议优先安排针对性讲解。
                      {selectedStatus.confusions.length > 0
                        ? "并结合上方混淆对进行易错概念辨析。"
                        : "若前置依赖仍为盲区，建议先回顾前置内容。"}
                    </p>
                  </div>
                )}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

function StatCard({
  icon,
  label,
  value,
  sub,
  cardClass,
  valueClass,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub: string;
  cardClass: string;
  valueClass: string;
}) {
  return (
    <div className={`rounded-lg border p-2.5 ${cardClass}`}>
      <div className="flex items-center gap-1.5 mb-1">
        {icon}
        <span className="text-[11px] text-muted-foreground font-normal tracking-wide">
          {label}
        </span>
      </div>
      <div className={`text-lg font-semibold ${valueClass}`}>{value}</div>
      <div className="text-[10px] text-muted-foreground">{sub}</div>
    </div>
  );
}

function LegendSwatch({ dotClass, label }: { dotClass: string; label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className={`h-2.5 w-2.5 rounded-full ${dotClass}`} />
      <span className="text-[11px] text-muted-foreground tracking-wide">{label}</span>
    </div>
  );
}

function ChapterCountDot({
  colorClass,
  count,
}: {
  colorClass: string;
  count: number;
}) {
  if (count === 0) return null;
  return (
    <span className="inline-flex items-center gap-1 text-[10px] text-muted-foreground/80 font-medium">
      <span className={`h-2 w-2 rounded-full ${colorClass}`} />
      {count}
    </span>
  );
}
