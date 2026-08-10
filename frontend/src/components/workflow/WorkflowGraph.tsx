import { useCallback, useMemo } from "react";
import {
  ReactFlow,
  Controls,
  Background,
  type Node,
  type Edge,
  Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { AgentNode, ExpertPhase, SessionStatus } from "@/types";
import { cn } from "@/lib/utils";

interface WorkflowGraphProps {
  intent?: "teach" | "chat" | "diagnose";
  workflowMode?: string;
  currentNode?: AgentNode | string;
  expertPhase?: ExpertPhase;
  status?: SessionStatus;
}

const nodeBase =
  "px-4 py-2 rounded-lg text-xs font-medium border shadow-sm transition-all duration-300";

const typeStyles: Record<string, string> = {
  init: "bg-slate-800 border-slate-600 text-slate-200",
  route: "bg-violet-950/60 border-violet-500/40 text-violet-200",
  diagnosis: "bg-amber-950/60 border-amber-500/40 text-amber-200",
  planner: "bg-blue-950/60 border-blue-500/40 text-blue-200",
  expert: "bg-cyan-950/60 border-cyan-500/40 text-cyan-200",
  barrier: "bg-slate-800 border-slate-600 text-slate-300",
  judge: "bg-rose-950/60 border-rose-500/40 text-rose-200",
  retrieval: "bg-emerald-950/60 border-emerald-500/40 text-emerald-200",
  chat: "bg-teal-950/60 border-teal-500/40 text-teal-200",
};

export function WorkflowGraph({
  intent = "teach",
  workflowMode,
  currentNode,
  expertPhase,
  status,
}: WorkflowGraphProps) {
  const isActive = useCallback(
    (nodeId: string) => {
      if (status && ["completed", "failed", "canceled"].includes(status)) {
        return false;
      }
      if (nodeId === currentNode) return true;
      if (
        nodeId === "expert_a" &&
        currentNode === "expert_a" &&
        expertPhase === "integration"
      )
        return true;
      return false;
    },
    [status, currentNode, expertPhase]
  );

  const isCompleted = useCallback(
    (nodeId: string) => {
      if (status === "completed") return true;
      const completedSet = new Set<string>();
      if (currentNode) completedSet.add(currentNode);
      if (currentNode === "planner") {
        completedSet.add("_init");
        completedSet.add("route");
        completedSet.add("diagnosis_feedback");
      }
      if (currentNode === "expert_a" || currentNode === "expert_b" || currentNode === "judge") {
        completedSet.add("_init");
        completedSet.add("route");
        completedSet.add("diagnosis_feedback");
        completedSet.add("planner");
      }
      return completedSet.has(nodeId);
    },
    [status, currentNode]
  );

  const nodes = useMemo(() => {
    const teachNodes: Node<{ label: string; phase?: string }>[] = [
      { id: "_init", position: { x: 50, y: 30 }, data: { label: "初始化" }, type: "default" },
      { id: "route", position: { x: 50, y: 110 }, data: { label: "意图路由" }, type: "default" },
      {
        id: "diagnosis_feedback",
        position: { x: 50, y: 190 },
        data: { label: "学情诊断" },
        type: "default",
      },
      { id: "planner", position: { x: 50, y: 270 }, data: { label: "路径规划" }, type: "default" },
      { id: "expert_a", position: { x: -80, y: 370 }, data: { label: "专家 A", phase: expertPhase }, type: "default" },
      { id: "expert_b", position: { x: 180, y: 370 }, data: { label: "专家 B", phase: expertPhase }, type: "default" },
      {
        id: "_experts_barrier",
        position: { x: 50, y: 470 },
        data: { label: "阶段汇合" },
        type: "default",
      },
      {
        id: "expert_a_integration",
        position: { x: 50, y: 560 },
        data: { label: "专家 A 整合" },
        type: "default",
      },
      { id: "judge", position: { x: 50, y: 650 }, data: { label: "审核裁判" }, type: "default" },
    ];

    const chatNodes: Node<{ label: string }>[] = [
      { id: "_init", position: { x: 50, y: 30 }, data: { label: "初始化" }, type: "default" },
      { id: "route", position: { x: 50, y: 110 }, data: { label: "意图路由" }, type: "default" },
      {
        id: "retrieve_context",
        position: { x: 50, y: 190 },
        data: { label: "RAG 检索" },
        type: "default",
      },
      {
        id: "chat_answer",
        position: { x: 50, y: 270 },
        data: { label: "快速问答" },
        type: "default",
      },
    ];

    const diagnoseNodes: Node<{ label: string }>[] = [
      { id: "_init", position: { x: 50, y: 30 }, data: { label: "初始化" }, type: "default" },
      { id: "route", position: { x: 50, y: 110 }, data: { label: "意图路由" }, type: "default" },
      {
        id: "diagnosis_feedback",
        position: { x: 50, y: 190 },
        data: { label: "学情诊断" },
        type: "default",
      },
    ];

    const feedbackNodes: Node<{ label: string }>[] = [
      { id: "_init", position: { x: 50, y: 30 }, data: { label: "初始化" }, type: "default" },
      {
        id: "diagnosis_feedback",
        position: { x: 50, y: 110 },
        data: { label: "反馈分析" },
        type: "default",
      },
    ];

    let selectedNodes = teachNodes;
    if (workflowMode === "feedback") selectedNodes = feedbackNodes;
    else if (intent === "chat") selectedNodes = chatNodes;
    else if (intent === "diagnose") selectedNodes = diagnoseNodes;

    const phaseLabels: Record<string, string> = {
      draft: "草稿",
      cross_review: "互评",
      revision: "修订",
      integration: "整合",
    };

    return selectedNodes.map((n) => {
      const active = isActive(n.id);
      const completed = isCompleted(n.id);
      const kind =
        n.id === "_init"
          ? "init"
          : n.id === "route"
          ? "route"
          : n.id === "diagnosis_feedback"
          ? "diagnosis"
          : n.id === "planner"
          ? "planner"
          : n.id.startsWith("expert")
          ? "expert"
          : n.id === "_experts_barrier"
          ? "barrier"
          : n.id === "judge"
          ? "judge"
          : n.id === "retrieve_context"
          ? "retrieval"
          : n.id === "chat_answer"
          ? "chat"
          : "init";

      return {
        ...n,
        data: {
          label: (
            <div className="flex flex-col items-center">
              <span>{n.data.label}</span>
              {n.data.phase && (
                <span className="mt-1 text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300">
                  {phaseLabels[n.data.phase] || n.data.phase}
                </span>
              )}
              {active && (
                <span className="mt-1.5 inline-flex items-center gap-1 rounded-full bg-cyan-500/30 px-2 py-0.5 text-[10px] font-semibold text-cyan-200">
                  <span className="relative flex h-2 w-2">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan-400 opacity-75" />
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-cyan-300" />
                  </span>
                  运行中
                </span>
              )}
            </div>
          ),
        },
        className: cn(
          nodeBase,
          typeStyles[kind],
          active &&
            "ring-4 ring-cyan-400/70 ring-offset-2 ring-offset-slate-950 scale-110 z-10",
          active && "shadow-[0_0_24px_4px_rgba(34,211,238,0.45)]",
          active && "bg-cyan-600 border-cyan-400 text-white",
          completed && !active && "opacity-70 border-white/10",
        ),
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
      };
    });
  }, [intent, workflowMode, isActive, isCompleted, expertPhase]);

  const edges: Edge[] = useMemo(() => {
    if (workflowMode === "feedback") {
      return [{ id: "e_init_feedback", source: "_init", target: "diagnosis_feedback" }];
    }
    if (intent === "chat") {
      return [
        { id: "e_init_route", source: "_init", target: "route" },
        { id: "e_route_retrieval", source: "route", target: "retrieve_context" },
        { id: "e_retrieval_chat", source: "retrieve_context", target: "chat_answer" },
      ];
    }
    if (intent === "diagnose") {
      return [
        { id: "e_init_route", source: "_init", target: "route" },
        { id: "e_route_diag", source: "route", target: "diagnosis_feedback" },
      ];
    }
    return [
      { id: "e_init_route", source: "_init", target: "route" },
      { id: "e_route_diag", source: "route", target: "diagnosis_feedback" },
      { id: "e_diag_planner", source: "diagnosis_feedback", target: "planner" },
      { id: "e_planner_a", source: "planner", target: "expert_a" },
      { id: "e_planner_b", source: "planner", target: "expert_b" },
      { id: "e_a_barrier", source: "expert_a", target: "_experts_barrier" },
      { id: "e_b_barrier", source: "expert_b", target: "_experts_barrier" },
      { id: "e_barrier_a", source: "_experts_barrier", target: "expert_a", label: "多阶段" },
      { id: "e_barrier_b", source: "_experts_barrier", target: "expert_b", label: "多阶段" },
      { id: "e_barrier_integration", source: "_experts_barrier", target: "expert_a_integration" },
      { id: "e_integration_judge", source: "expert_a_integration", target: "judge" },
    ];
  }, [intent, workflowMode]);

  return (
    <div className="h-full w-full rounded-xl border border-white/5 bg-slate-950/50">
      <ReactFlow
        nodes={nodes}
        edges={edges}
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