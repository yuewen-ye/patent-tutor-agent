import { useMemo } from "react";
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

interface LearningPathGraphProps {
  path: LearningPathItem[];
  mastery?: Record<string, number>;
}

const getNodeColor = (masteryValue?: number) => {
  if (masteryValue === undefined) return "bg-slate-800 border-slate-600 text-slate-200";
  if (masteryValue >= 0.85) return "bg-emerald-950/60 border-emerald-500/40 text-emerald-200";
  if (masteryValue >= 0.5) return "bg-cyan-950/60 border-cyan-500/40 text-cyan-200";
  return "bg-amber-950/60 border-amber-500/40 text-amber-200";
};

export function LearningPathGraph({ path }: LearningPathGraphProps) {
  const { nodes, edges } = useMemo(() => {
    const gapX = 260;
    const gapY = 140;

    const generatedNodes: Node[] = path.map((item, index) => {
      const row = Math.floor(index / 3);
      const col = index % 3;
      const y = row * gapY + 20;
      const reverseCol = row % 2 === 1 ? 2 - col : col;
      const finalX = reverseCol * gapX + 20;

      return {
        id: item.node_id,
        position: { x: finalX, y },
        data: { item, index },
        type: "pathNode",
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
      };
    });

    const generatedEdges: Edge[] = [];
    for (let i = 0; i < path.length - 1; i++) {
      generatedEdges.push({
        id: `e-${path[i].node_id}-${path[i + 1].node_id}`,
        source: path[i].node_id,
        target: path[i + 1].node_id,
        animated: true,
        style: { stroke: "#22d3ee", strokeWidth: 2, opacity: 0.6 },
      });
    }

    return { nodes: generatedNodes, edges: generatedEdges };
  }, [path]);

  const nodeTypes = useMemo(
    () => ({
      pathNode: PathNode,
    }),
    []
  );

  return (
    <div className="h-[520px] w-full rounded-xl border border-white/5 bg-slate-950/50">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        attributionPosition="bottom-left"
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#334155" gap={20} size={1} />
        <Controls className="!bg-slate-900 !border-slate-700" />
      </ReactFlow>
    </div>
  );
}

function PathNode({ data }: { data: { item: LearningPathItem; index: number } }) {
  const { item, index } = data;
  // Placeholder mastery - in real app would lookup by node_id
  const masteryValue = undefined;

  return (
    <div
      className={cn(
        "w-[200px] rounded-lg border p-3 shadow-lg transition-all hover:scale-[1.02]",
        getNodeColor(masteryValue)
      )}
    >
      <Handle type="target" position={Position.Top} className="!bg-cyan-400" />
      <div className="flex items-center gap-2 mb-1">
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-white/10 text-xs font-bold">
          {index + 1}
        </span>
        <span className="text-xs font-medium truncate">{item.node_name}</span>
      </div>
      <div className="text-[10px] opacity-80 line-clamp-2">{item.strategy}</div>
      <div className="mt-2 flex items-center justify-between text-[10px] opacity-70">
        <span>{item.duration_min} 分钟</span>
        <span>{item.prerequisites.length > 0 ? `前置 ${item.prerequisites.length}` : "无前置"}</span>
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-cyan-400" />
    </div>
  );
}
