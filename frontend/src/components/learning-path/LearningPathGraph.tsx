import { useMemo, useState } from "react";
import {
  ReactFlow,
  Controls,
  Background,
  type Node,
  type Edge,
  Position,
  Handle,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { LearningPathItem } from "@/types";
import { cn } from "@/lib/utils";
import { Maximize2, Minimize2 } from "lucide-react";

interface LearningPathGraphProps {
  path: LearningPathItem[];
  pathDecision?: Record<string, unknown>;
  mastery?: Record<string, number>;
}

const WINDOW_SIZE = 4;

function parsePathDecision(pd?: Record<string, unknown>) {
  if (!pd) return { currentNodeId: undefined, completedIds: new Set<string>() };
  const current = typeof pd.current_node_id === "string" ? pd.current_node_id : undefined;
  const completedRaw = pd.completed_node_ids;
  const completedIds = new Set<string>(
    Array.isArray(completedRaw)
      ? completedRaw.filter((v): v is string => typeof v === "string")
      : []
  );
  return { currentNodeId: current, completedIds };
}

function resolveWindow(path: LearningPathItem[], currentNodeId?: string, showAll = false) {
  if (!path.length) return { window: [], startIndex: 0, total: 0 };
  if (showAll) return { window: path, startIndex: 0, total: path.length };
  if (!currentNodeId) {
    return { window: path.slice(0, WINDOW_SIZE), startIndex: 0, total: path.length };
  }
  const idx = path.findIndex((p) => p.node_id === currentNodeId);
  if (idx < 0) {
    return { window: path.slice(0, WINDOW_SIZE), startIndex: 0, total: path.length };
  }
  const start = Math.max(0, idx - 1);
  const end = Math.min(path.length, start + WINDOW_SIZE);
  return { window: path.slice(start, end), startIndex: start, total: path.length };
}

function getNodeStyle(state: "completed" | "current" | "pending") {
  switch (state) {
    case "completed":
      return "border-emerald-500/70 bg-emerald-50 text-emerald-800";
    case "current":
      return "border-[#D9773E] bg-[#D9773E] text-white shadow-[0_4px_16px_rgba(217,119,62,0.35)] scale-[1.05] ring-2 ring-[#F4A261]/60";
    case "pending":
    default:
      return "border-slate-300 bg-white text-slate-800 shadow-sm";
  }
}

export function LearningPathGraph({ path, pathDecision }: LearningPathGraphProps) {
  const [showAll, setShowAll] = useState(false);
  const { currentNodeId, completedIds } = useMemo(() => parsePathDecision(pathDecision), [pathDecision]);
  const { window: displayPath, startIndex, total } = useMemo(
    () => resolveWindow(path, currentNodeId, showAll),
    [path, currentNodeId, showAll]
  );

  const { nodes, edges } = useMemo(() => {
    const currentIdx = path.findIndex((p) => p.node_id === currentNodeId);

    const canBeCompleted = (nodeId: string) => {
      const itemIdx = path.findIndex((p) => p.node_id === nodeId);
      return currentIdx >= 0 && itemIdx >= 0 && itemIdx < currentIdx;
    };

    let generatedNodes: Node[];
    let generatedEdges: Edge[];

    if (showAll) {
      const COLS = Math.min(6, displayPath.length);
      const gapX = 190;
      const gapY = 110;
      generatedNodes = displayPath.map((item, index) => {
        let state: "completed" | "current" | "pending" = "pending";
        if (item.node_id === currentNodeId) state = "current";
        else if (canBeCompleted(item.node_id) && completedIds.has(item.node_id)) state = "completed";

        const row = Math.floor(index / COLS);
        const orderCol = index % COLS;
        const isRightToLeft = row % 2 === 1;
        const col = isRightToLeft ? COLS - 1 - orderCol : orderCol;

        const isLastInRow = orderCol === COLS - 1 || index === displayPath.length - 1;
        const isFirstInRow = orderCol === 0;

        let sourcePos: Position;
        if (isLastInRow) sourcePos = Position.Bottom;
        else sourcePos = isRightToLeft ? Position.Left : Position.Right;

        let targetPos: Position;
        if (isFirstInRow && index > 0) targetPos = Position.Top;
        else targetPos = isRightToLeft ? Position.Right : Position.Left;

        return {
          id: item.node_id,
          position: { x: col * gapX + 40, y: row * gapY + 40 },
          data: { item, globalIndex: index, state, total, showAll, sourcePos, targetPos },
          type: "pathNode",
          sourcePosition: sourcePos,
          targetPosition: targetPos,
        };
      });

      generatedEdges = [];
      for (let i = 0; i < displayPath.length - 1; i++) {
        const sourceIsForward = currentIdx < 0 || i >= currentIdx;
        generatedEdges.push({
          id: `e-${displayPath[i].node_id}-${displayPath[i + 1].node_id}`,
          source: displayPath[i].node_id,
          target: displayPath[i + 1].node_id,
          animated: sourceIsForward,
          style: {
            stroke: sourceIsForward ? "#D9773E" : "#94a3b8",
            strokeWidth: sourceIsForward ? 2.5 : 1.5,
            opacity: sourceIsForward ? 0.9 : 0.5,
          },
        });
      }
    } else {
      const gapX = 260;
      const fixedY = 100;
      generatedNodes = displayPath.map((item, index) => {
        let state: "completed" | "current" | "pending" = "pending";
        if (item.node_id === currentNodeId) state = "current";
        else if (canBeCompleted(item.node_id) && completedIds.has(item.node_id)) state = "completed";

        return {
          id: item.node_id,
          position: { x: index * gapX + 40, y: fixedY },
          data: { item, globalIndex: startIndex + index, state, total, showAll: false },
          type: "pathNode",
          sourcePosition: Position.Right,
          targetPosition: Position.Left,
        };
      });

      generatedEdges = [];
      for (let i = 0; i < displayPath.length - 1; i++) {
        const sourceIsForward = currentIdx < 0 || startIndex + i >= currentIdx;
        generatedEdges.push({
          id: `e-${displayPath[i].node_id}-${displayPath[i + 1].node_id}`,
          source: displayPath[i].node_id,
          target: displayPath[i + 1].node_id,
          animated: sourceIsForward,
          style: {
            stroke: sourceIsForward ? "#D9773E" : "#94a3b8",
            strokeWidth: sourceIsForward ? 2.5 : 1.5,
            opacity: sourceIsForward ? 0.9 : 0.5,
          },
        });
      }
    }

    return { nodes: generatedNodes, edges: generatedEdges };
  }, [displayPath, currentNodeId, completedIds, startIndex, path, showAll, total]);

  const nodeTypes = useMemo(
    () => ({
      pathNode: PathNode,
    }),
    []
  );

  const headerProgress = showAll
    ? `全部 ${total} 个节点`
    : currentNodeId
      ? `${startIndex + 1}-${Math.min(startIndex + displayPath.length, total)} / ${total}`
      : `前 ${displayPath.length} 个节点 / 共 ${total}`;

  return (
    <div className="w-full rounded-xl border border-slate-200 bg-white relative overflow-hidden">
      <div className="h-[340px] relative">
        <div className="absolute top-2.5 right-3 z-10 flex items-center gap-1.5">
          <div className="text-[11px] text-slate-600 bg-white/95 backdrop-blur px-2.5 py-1 rounded-md border border-slate-200 shadow-sm">
            {headerProgress}
            {!showAll && currentNodeId && (
              <span className="ml-2 text-[#D9773E]">● 当前</span>
            )}
          </div>
          <button
            type="button"
            onClick={() => setShowAll((v) => !v)}
            className="flex items-center gap-1 text-[11px] text-slate-600 bg-white/95 backdrop-blur px-2 py-1 rounded-md border border-slate-200 shadow-sm hover:bg-slate-50 transition-colors"
            title={showAll ? "返回聚焦视图" : "查看完整路径"}
          >
            {showAll ? <Minimize2 className="h-3 w-3" /> : <Maximize2 className="h-3 w-3" />}
            {showAll ? "聚焦" : "全部"}
          </button>
        </div>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          attributionPosition="bottom-left"
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#e2e8f0" gap={22} size={1.2} />
          <Controls className="!bg-white !border-slate-200 !text-slate-700 !shadow-sm [&>button]:!border-slate-200 [&>button]:!bg-white [&>button:hover]:!bg-slate-100" />
        </ReactFlow>
      </div>
      <div className="h-[40px] flex items-center justify-center gap-5 border-t border-slate-200 bg-slate-50 text-[11px] text-slate-600">
        <LegendSwatch className="bg-[#D9773E] ring-1 ring-[#F4A261]" label="当前节点" textClass="text-slate-700" />
        <LegendSwatch className="bg-emerald-50 border border-emerald-500/60" label="已完成" textClass="text-emerald-700" />
        <LegendSwatch className="bg-white border border-slate-300" label="待学习" textClass="text-slate-700" />
        <span className="ml-2 flex items-center gap-1.5 text-slate-500">
          <span className="inline-block w-5 h-[2px] bg-[#D9773E]" /> 前进方向
          <span className="inline-block w-5 h-[2px] bg-slate-400 ml-1" /> 已走过
        </span>
      </div>
    </div>
  );
}

function LegendSwatch({ className, label, textClass }: { className: string; label: string; textClass?: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={cn("inline-block w-3.5 h-3.5 rounded-sm", className)} />
      <span className={cn(textClass)}>{label}</span>
    </span>
  );
}

function PathNode({ data }: { data: { item: LearningPathItem; globalIndex: number; state: "completed" | "current" | "pending"; total: number; showAll?: boolean; sourcePos?: Position; targetPos?: Position } }) {
  const { item, globalIndex, state, showAll } = data;
  const style = getNodeStyle(state);

  const handleColor =
    state === "current" ? "!bg-[#F4A261]" :
    state === "completed" ? "!bg-emerald-500" :
    "!bg-slate-400";

  if (showAll) {
    const { sourcePos = Position.Right, targetPos = Position.Left } = data;
    const titleText =
      state === "current" ? "text-white" :
      state === "completed" ? "text-emerald-800" :
      "text-slate-800";
    return (
      <div
        className={cn(
          "w-[150px] rounded-md border px-2 py-1.5 shadow-sm transition-all duration-300",
          style
        )}
      >
        <Handle type="target" position={targetPos} className={cn("!w-2 !h-2 !rounded-full !border-0", handleColor)} />
        <div className="flex items-center gap-1.5">
          <span
            className={cn(
              "flex h-4 w-4 items-center justify-center rounded-full text-[10px] font-bold shrink-0",
              state === "current" ? "bg-white/25 text-white" :
              state === "completed" ? "bg-emerald-500/20 text-emerald-700" :
              "bg-slate-100 text-slate-600"
            )}
          >
            {globalIndex + 1}
          </span>
          <span className={cn("text-[11px] font-semibold truncate leading-tight", titleText)}>
            {item.node_name}
          </span>
        </div>
        <Handle type="source" position={sourcePos} className={cn("!w-2 !h-2 !rounded-full !border-0", handleColor)} />
      </div>
    );
  }

  const secondaryText =
    state === "current" ? "text-white/85" :
    state === "completed" ? "text-emerald-700/85" :
    "text-slate-500";

  const numBadge =
    state === "current" ? "bg-white/25 text-white" :
    state === "completed" ? "bg-emerald-500/20 text-emerald-700" :
    "bg-slate-100 text-slate-600";

  const titleText =
    state === "current" ? "text-white" :
    state === "completed" ? "text-emerald-800" :
    "text-slate-800";

  return (
    <div
      className={cn(
        "w-[210px] rounded-lg border p-3 shadow-md transition-all duration-300",
        style
      )}
    >
      <Handle type="target" position={Position.Left} className={cn("!w-2.5 !h-2.5 !rounded-full !border-0", handleColor)} />
      <div className="flex items-center gap-2 mb-1.5">
        <span className={cn("flex h-5 w-5 items-center justify-center rounded-full text-xs font-bold shrink-0", numBadge)}>
          {globalIndex + 1}
        </span>
        <span className={cn("text-sm font-semibold truncate", titleText)}>
          {item.node_name}
        </span>
      </div>
      <div className={cn("text-[11px] leading-relaxed line-clamp-2", secondaryText)}>
        {item.strategy}
      </div>
      <div className={cn("mt-2.5 flex items-center justify-between text-[11px]", secondaryText)}>
        <span>{item.duration_min} 分钟</span>
        <span>{item.prerequisites.length > 0 ? `前置 ${item.prerequisites.length}` : "无前置"}</span>
      </div>
      <Handle type="source" position={Position.Right} className={cn("!w-2.5 !h-2.5 !rounded-full !border-0", handleColor)} />
    </div>
  );
}
