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

const pendingNode = "bg-slate-900/70 border-slate-700/50 text-slate-500";
const completedNode = "bg-slate-800/60 border-slate-600/50 text-slate-400";
const activeNode =
  "bg-[#D9773E] border-[#F4A261] text-white shadow-[0_0_24px_4px_rgba(217,119,62,0.55)]";

// 并行阶段：专家 A/B 同时运行的阶段
const PARALLEL_PHASES: readonly string[] = ["draft", "cross_review", "revision"];

// 根据 currentNode + expertPhase 推断所有已完成的节点集合
function buildCompletedSet(
  currentNode: string | undefined,
  expertPhase: ExpertPhase | undefined,
  status: SessionStatus | undefined
): Set<string> {
  if (status === "completed") {
    return new Set([
      "_init", "route", "diagnosis_feedback", "planner",
      "expert_a", "expert_b", "_experts_barrier",
      "expert_a_integration", "judge", "slide_deck", "generate_pptx",
    ]);
  }
  const done = new Set<string>();
  if (!currentNode) return done;

  // 基础线性链路：_init → route → diagnosis_feedback → planner
  switch (currentNode) {
    case "_init":
      break;
    case "route":
      done.add("_init");
      break;
    case "diagnosis_feedback":
      done.add("_init");
      done.add("route");
      break;
    case "planner":
      done.add("_init");
      done.add("route");
      done.add("diagnosis_feedback");
      break;
    case "retrieve_context":
    case "chat_answer":
      done.add("_init");
      done.add("route");
      break;
    case "expert_a":
    case "expert_b": {
      // 专家并行阶段
      done.add("_init");
      done.add("route");
      done.add("diagnosis_feedback");
      done.add("planner");
      // barrier 是否已完成取决于当前 phase
      // draft: barrier 还没运行过
      // cross_review/revision: barrier 已完成（上一阶段的汇合）
      if (expertPhase === "cross_review" || expertPhase === "revision") {
        done.add("_experts_barrier");
        // 上一阶段的专家也已完成
        done.add("expert_a");
        done.add("expert_b");
      }
      // 注意：并行阶段当前运行的专家不算完成
      break;
    }
    case "_experts_barrier": {
      // barrier 运行时，两个专家刚刚完成
      done.add("_init");
      done.add("route");
      done.add("diagnosis_feedback");
      done.add("planner");
      done.add("expert_a");
      done.add("expert_b");
      // 如果在 cross_review/revision，之前的 barrier 也完成了
      if (expertPhase === "revision") {
        // barrier 在 revision 阶段前已运行过 1 次
        // 但 _experts_barrier 本身在图中是单一节点，已完成状态由 expertPhase 决定
      }
      break;
    }
    case "expert_a_integration": {
      // integration 阶段：所有并行阶段均已完成
      done.add("_init");
      done.add("route");
      done.add("diagnosis_feedback");
      done.add("planner");
      done.add("expert_a");
      done.add("expert_b");
      done.add("_experts_barrier");
      break;
    }
    case "judge": {
      done.add("_init");
      done.add("route");
      done.add("diagnosis_feedback");
      done.add("planner");
      done.add("expert_a");
      done.add("expert_b");
      done.add("_experts_barrier");
      done.add("expert_a_integration");
      break;
    }
    case "slide_deck": {
      done.add("_init");
      done.add("route");
      done.add("diagnosis_feedback");
      done.add("planner");
      done.add("expert_a");
      done.add("expert_b");
      done.add("_experts_barrier");
      done.add("expert_a_integration");
      done.add("judge");
      break;
    }
    case "generate_pptx": {
      done.add("_init");
      done.add("route");
      done.add("diagnosis_feedback");
      done.add("planner");
      done.add("expert_a");
      done.add("expert_b");
      done.add("_experts_barrier");
      done.add("expert_a_integration");
      done.add("judge");
      done.add("slide_deck");
      break;
    }
    default:
      break;
  }
  return done;
}

export function WorkflowGraph({
  intent = "teach",
  workflowMode,
  currentNode,
  expertPhase,
  status,
}: WorkflowGraphProps) {
  // 是否已结束
  const isFinished = Boolean(status && ["completed", "failed", "canceled"].includes(status));

  // 并行阶段判断：draft/cross_review/revision 中专家 A/B 同时运行
  const isExpertParallel =
    !isFinished &&
    (currentNode === "expert_a" || currentNode === "expert_b") &&
    Boolean(expertPhase && PARALLEL_PHASES.includes(expertPhase));

  // integration 阶段判断：currentNode 是 expert_a（node_label 映射），但实际节点是 expert_a_integration
  const isIntegration =
    !isFinished &&
    currentNode === "expert_a" &&
    expertPhase === "integration";

  // 已完成节点集合
  const completedSet = useMemo(
    () => buildCompletedSet(currentNode, expertPhase, status),
    [currentNode, expertPhase, status]
  );

  const isActive = useCallback(
    (nodeId: string) => {
      if (isFinished) return false;
      // integration 阶段：expert_a_integration 节点运行中
      if (isIntegration) {
        return nodeId === "expert_a_integration";
      }
      // 并行阶段：两个专家同时高亮
      if (isExpertParallel) {
        return nodeId === "expert_a" || nodeId === "expert_b";
      }
      // barrier 节点
      if (nodeId === "_experts_barrier" && currentNode === "_experts_barrier") return true;
      // 默认：currentNode 匹配
      if (nodeId === currentNode) return true;
      return false;
    },
    [isFinished, isIntegration, isExpertParallel, currentNode]
  );

  const isCompleted = useCallback(
    (nodeId: string) => {
      if (isFinished && status === "completed") return true;
      // 并行阶段：正在运行的专家不算完成
      if (isExpertParallel && (nodeId === "expert_a" || nodeId === "expert_b")) {
        return false;
      }
      // integration 阶段：expert_a 本身不算完成（是 expert_a_integration 在运行）
      if (isIntegration && nodeId === "expert_a") {
        return false;
      }
      return completedSet.has(nodeId);
    },
    [isFinished, status, isExpertParallel, isIntegration, completedSet]
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
      {
        id: "expert_a",
        position: { x: -80, y: 370 },
        data: { label: "专家 A", phase: expertPhase },
        type: "default",
      },
      {
        id: "expert_b",
        position: { x: 180, y: 370 },
        data: { label: "专家 B", phase: expertPhase },
        type: "default",
      },
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
      {
        id: "judge",
        position: { x: 50, y: 650 },
        data: { label: "审核裁判" },
        type: "default",
      },
      {
        id: "slide_deck",
        position: { x: -80, y: 730 },
        data: { label: "课件生成" },
        type: "default",
      },
      {
        id: "generate_pptx",
        position: { x: 180, y: 730 },
        data: { label: "PPT 渲染" },
        type: "default",
      },
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

      let style: string;
      if (active) style = activeNode;
      else if (completed) style = completedNode;
      else style = pendingNode;

      return {
        ...n,
        data: {
          label: (
            <div className="flex flex-col items-center">
              <span>{n.data.label}</span>
              {n.data.phase && (
                <span
                  className={cn(
                    "mt-1 text-[10px] px-1.5 py-0.5 rounded",
                    active
                      ? "bg-white/25 text-white"
                      : completed
                      ? "bg-slate-700/50 text-slate-400"
                      : "bg-slate-800/60 text-slate-500"
                  )}
                >
                  {phaseLabels[n.data.phase] || n.data.phase}
                </span>
              )}
              {active && (
                <span className="mt-1.5 inline-flex items-center gap-1 rounded-full bg-white/25 px-2 py-0.5 text-[10px] font-semibold text-white">
                  <span className="relative flex h-2 w-2">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-white opacity-75" />
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-white" />
                  </span>
                  运行中
                </span>
              )}
            </div>
          ),
        },
        className: cn(
          nodeBase,
          style,
          active && "ring-2 ring-[#F4A261] ring-offset-2 ring-offset-slate-950 scale-110 z-10",
        ),
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
      };
    });
  }, [intent, workflowMode, isActive, isCompleted, expertPhase]);

  const edges: Edge[] = useMemo(() => {
    const raw: Edge[] = (() => {
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
      // teach 模式完整链路
      return [
        { id: "e_init_route", source: "_init", target: "route" },
        { id: "e_route_diag", source: "route", target: "diagnosis_feedback" },
        { id: "e_diag_planner", source: "diagnosis_feedback", target: "planner" },
        // 并行分叉
        { id: "e_planner_a", source: "planner", target: "expert_a" },
        { id: "e_planner_b", source: "planner", target: "expert_b" },
        // 并行汇合
        { id: "e_a_barrier", source: "expert_a", target: "_experts_barrier" },
        { id: "e_b_barrier", source: "expert_b", target: "_experts_barrier" },
        // barrier → 下一轮并行（cross_review / revision）或 → integration
        { id: "e_barrier_a", source: "_experts_barrier", target: "expert_a" },
        { id: "e_barrier_b", source: "_experts_barrier", target: "expert_b" },
        { id: "e_barrier_integration", source: "_experts_barrier", target: "expert_a_integration" },
        // integration → judge → slide_deck → generate_pptx
        { id: "e_integration_judge", source: "expert_a_integration", target: "judge" },
        { id: "e_judge_slide_deck", source: "judge", target: "slide_deck" },
        { id: "e_slide_deck_pptx", source: "slide_deck", target: "generate_pptx" },
      ];
    })();

    return raw.map((e) => {
      const srcActive = isActive(e.source);
      const tgtActive = isActive(e.target);
      const isHot = srcActive || tgtActive;
      return {
        ...e,
        type: "smoothstep",
        animated: false,
        style: isHot
          ? { stroke: "#94a3b8", strokeWidth: 2.5 } // 激活边：更亮的灰蓝色粗实线
          : { stroke: "#475569", strokeWidth: 1.5 }, // 普通边：清晰的深灰色实线
      };
    });
  }, [intent, workflowMode, isActive]);

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
