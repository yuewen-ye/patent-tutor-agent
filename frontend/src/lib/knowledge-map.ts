import type { SunburstTreeNode } from "@/components/profile/sunburst-tree";
import { SUNBURST_TREE } from "@/components/profile/sunburst-tree";

export const NODE_NAME_MAP: Record<string, string> = {
  "patent-law-foundation": "专利法律制度基础",
  "patent-system-overview": "专利制度概论",
  "patent-law-framework": "专利法律体系",
  "patent-rights-nature": "专利权的性质与特征",
  "patentability-substantive": "专利授权实质条件",
  novelty: "新颖性",
  "prior-art-definition": "现有技术认定",
  "conflicting-application": "抵触申请",
  "grace-period": "不丧失新颖性的宽限期",
  "inventive-step": "创造性",
  "three-step-method": "创造性三步法判断",
  "person-skilled-in-art": "所属技术领域的技术人员",
  "practical-applicability": "实用性",
  "design-patentability": "外观设计授权条件",
  "non-patentable-subject": "不授予专利权的主题",
  "scientific-discovery-vs-invention": "科学发现与发明创造的区分",
  "medical-method-exclusion": "疾病诊疗方法的排除",
  "public-order-morality": "公共秩序与道德条款",
  "patent-application-process": "专利申请程序",
  "application-documents": "专利申请文件要求",
  "specification-requirements": "说明书撰写要求",
  "claims-drafting-basics": "权利要求书撰写基础",
  "priority-right": "优先权制度",
  "filing-date": "申请日的确定",
  "divisional-application": "分案申请",
  "patent-examination": "专利审查流程",
  "preliminary-examination": "初步审查",
  "substantive-examination": "实质审查",
  "office-action-response": "审查意见答复",
  "amendment-limits": "专利申请文件的修改限制",
  "patent-reexamination": "专利复审程序",
  "reexamination-request": "复审请求的提出",
  "collegial-review": "合议审查与复审决定",
  "patent-invalidation": "专利无效宣告",
  "invalidation-grounds": "无效宣告理由",
  "oral-proceeding": "口头审理程序",
  "patent-rights-protection": "专利权保护",
  "protection-scope": "专利权保护范围",
  "doctrine-of-equivalents": "等同原则",
  "claim-interpretation": "权利要求解释规则",
  "infringement-types": "专利侵权行为类型",
  "infringement-defenses": "侵权抗辩事由",
  "bolar-exemption": "Bolar例外",
  "prior-use-right": "先用权",
  remedies: "侵权救济",
  "patent-agency-practice": "专利代理实务",
  "claims-drafting-advanced": "权利要求撰写实务",
  "oa-response-practice": "审查意见答复实务",
  "invalidation-practice": "无效宣告实务",
  "related-laws": "相关法律知识",
  "civil-law-basics": "民法基础",
  "contract-law-tech": "技术合同法",
  "administrative-procedure": "行政法与行政诉讼",
  "civil-procedure": "民事诉讼程序",
  "trips-agreement": "TRIPS协定",
  "pct-system": "PCT国际申请",
  "pct-filing": "PCT国际申请程序",
  "pct-national-phase": "PCT国家阶段",
  "foreign-priority": "外国优先权",
  "domestic-priority": "本国优先权",
  "scientific-research-exemption": "科学实验使用例外",
  "direct-infringement": "直接侵权",
  "indirect-infringement": "间接侵权",
  "independent-claim": "独立权利要求",
  "dependent-claim": "从属权利要求",
  "employee-invention": "职务发明",
  "exhaustion-of-rights": "权利用尽",
  "implied-license": "默示许可",
  "general-consumer": "一般消费者",
};

export function nodeIdToName(nodeId: string): string {
  return NODE_NAME_MAP[nodeId] ?? nodeId;
}

export type KnowledgeState = "blind_spot" | "learning" | "mastered" | "unknown";

export interface KnowledgeNodeStatus {
  pl: number;
  state: KnowledgeState;
}

export function classifyMastery(pl: number | undefined | null): KnowledgeNodeStatus {
  if (pl === undefined || pl === null || Number.isNaN(pl)) {
    return { pl: 0, state: "unknown" };
  }
  if (pl < 0.4) return { pl, state: "blind_spot" };
  if (pl < 0.8) return { pl, state: "learning" };
  return { pl, state: "mastered" };
}

/**
 * 从 masterySnapshot 中的原始值抽取 P(L) 掌握概率数值。
 *
 * 兼容两种后端返回格式：
 *   1) 扁平数字格式（learner.mastery）：Record<string, number>
 *   2) 嵌套对象格式（diagnostic.knowledge_snapshot）：Record<string, { pl: number }>
 */
export function extractPl(raw: unknown): number | undefined {
  if (typeof raw === "number" && !Number.isNaN(raw)) return raw;
  if (raw && typeof raw === "object") {
    const obj = raw as Record<string, unknown>;
    const pl = obj.pl;
    if (typeof pl === "number" && !Number.isNaN(pl)) return pl;
  }
  return undefined;
}

export interface ChapterGroup {
  chapterId: string;
  chapterName: string;
  nodes: Array<{ nodeId: string; nodeName: string }>;
}

export function buildChapterGroups(tree: SunburstTreeNode[] = SUNBURST_TREE): ChapterGroup[] {
  const groups: ChapterGroup[] = [];
  const collectLeaves = (node: SunburstTreeNode, acc: Array<{ nodeId: string; nodeName: string }>) => {
    if (!node.children || node.children.length === 0) {
      acc.push({ nodeId: node.englishId, nodeName: node.name });
      return;
    }
    for (const child of node.children) {
      collectLeaves(child, acc);
    }
  };
  for (const chapter of tree) {
    const nodes: Array<{ nodeId: string; nodeName: string }> = [];
    collectLeaves(chapter, nodes);
    if (nodes.length > 0) {
      groups.push({
        chapterId: chapter.englishId,
        chapterName: chapter.name,
        nodes,
      });
    }
  }
  return groups;
}

export interface MasteryStats {
  blindSpotCount: number;
  learningCount: number;
  masteredCount: number;
  unknownCount: number;
  totalCount: number;
  blindSpotRate: number;
  avgMastery: number;
}

export function computeMasteryStats(
  groups: ChapterGroup[],
  masterySnapshot: Record<string, unknown> | undefined | null,
): MasteryStats {
  // 统计范围：SUNBURST_TREE 的叶子节点 key 合并 masterySnapshot 中的有效 key（并集去重）
  // 这样保证 BlindSpotGraph（叶子视图）与 MasterySunburst（含父节点 key 的 mastery）使用的样本空间一致。
  const keysToEvaluate = new Set<string>();
  for (const group of groups) {
    for (const n of group.nodes) keysToEvaluate.add(n.nodeId);
  }
  if (masterySnapshot) {
    for (const k of Object.keys(masterySnapshot)) {
      if (extractPl(masterySnapshot[k]) !== undefined) keysToEvaluate.add(k);
    }
  }

  let blindSpotCount = 0;
  let learningCount = 0;
  let masteredCount = 0;
  let unknownCount = 0;
  let totalCount = 0;
  let plSum = 0;
  let covered = 0;
  for (const key of keysToEvaluate) {
    totalCount += 1;
    const raw = masterySnapshot?.[key];
    const pl = extractPl(raw);
    const { state } = classifyMastery(pl);
    if (state === "blind_spot") blindSpotCount += 1;
    else if (state === "learning") learningCount += 1;
    else if (state === "mastered") masteredCount += 1;
    else unknownCount += 1;
    if (pl !== undefined) {
      plSum += pl;
      covered += 1;
    }
  }
  return {
    blindSpotCount,
    learningCount,
    masteredCount,
    unknownCount,
    totalCount,
    blindSpotRate: totalCount === 0 ? 0 : blindSpotCount / totalCount,
    avgMastery: covered === 0 ? 0 : plSum / covered,
  };
}

export function masteryStateColor(state: KnowledgeState): string {
  switch (state) {
    case "blind_spot":
      return "text-rose-600";
    case "learning":
      return "text-amber-600";
    case "mastered":
      return "text-emerald-600";
    default:
      return "text-slate-500";
  }
}
