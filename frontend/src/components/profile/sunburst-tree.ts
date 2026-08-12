export interface SunburstTreeNode {
  name: string;
  englishId: string;
  value?: number;
  children?: SunburstTreeNode[];
}

// 由 backend/app/curriculum/data/knowledge-dag.json 生成的层级树（知识点的包含关系）。
// englishId 与后端 BKT mastery 的 key 一致，用于将真实掌握度映射到旭日图。
export const SUNBURST_TREE: SunburstTreeNode[] = [
  {
    name: "专利法律制度基础",
    englishId: "patent-law-foundation",
    children: [
      {
        name: "专利制度概论",
        englishId: "patent-system-overview",
        value: 1.0,
      },
      {
        name: "专利法律体系",
        englishId: "patent-law-framework",
        value: 1.0,
      },
      {
        name: "专利权的性质与特征",
        englishId: "patent-rights-nature",
        value: 1.0,
      },
    ],
  },
  {
    name: "专利授权实质条件",
    englishId: "patentability-substantive",
    children: [
      {
        name: "新颖性",
        englishId: "novelty",
        children: [
          {
            name: "现有技术认定",
            englishId: "prior-art-definition",
            value: 1.0,
          },
          {
            name: "抵触申请",
            englishId: "conflicting-application",
            value: 1.0,
          },
          {
            name: "不丧失新颖性的宽限期",
            englishId: "grace-period",
            value: 0.5,
          },
        ],
      },
      {
        name: "创造性",
        englishId: "inventive-step",
        children: [
          {
            name: "创造性三步法判断",
            englishId: "three-step-method",
            value: 1.5,
          },
          {
            name: "所属技术领域的技术人员",
            englishId: "person-skilled-in-art",
            value: 0.5,
          },
        ],
      },
      {
        name: "实用性",
        englishId: "practical-applicability",
        value: 1.0,
      },
      {
        name: "外观设计授权条件",
        englishId: "design-patentability",
        value: 1.5,
      },
      {
        name: "不授予专利权的主题",
        englishId: "non-patentable-subject",
        children: [
          {
            name: "科学发现与发明创造的区分",
            englishId: "scientific-discovery-vs-invention",
            value: 0.5,
          },
          {
            name: "疾病诊疗方法的排除",
            englishId: "medical-method-exclusion",
            value: 0.5,
          },
          {
            name: "公共秩序与道德条款",
            englishId: "public-order-morality",
            value: 0.5,
          },
        ],
      },
    ],
  },
  {
    name: "专利申请程序",
    englishId: "patent-application-process",
    children: [
      {
        name: "专利申请文件要求",
        englishId: "application-documents",
        children: [
          {
            name: "说明书撰写要求",
            englishId: "specification-requirements",
            value: 1.0,
          },
          {
            name: "权利要求书撰写基础",
            englishId: "claims-drafting-basics",
            value: 1.5,
          },
        ],
      },
      {
        name: "优先权制度",
        englishId: "priority-right",
        value: 1.5,
      },
      {
        name: "申请日的确定",
        englishId: "filing-date",
        value: 0.5,
      },
      {
        name: "分案申请",
        englishId: "divisional-application",
        value: 1.0,
      },
    ],
  },
  {
    name: "专利审查流程",
    englishId: "patent-examination",
    children: [
      {
        name: "初步审查",
        englishId: "preliminary-examination",
        value: 1.0,
      },
      {
        name: "实质审查",
        englishId: "substantive-examination",
        value: 2.5,
      },
      {
        name: "审查意见答复",
        englishId: "office-action-response",
        children: [
          {
            name: "专利申请文件的修改限制",
            englishId: "amendment-limits",
            value: 1.0,
          },
        ],
      },
    ],
  },
  {
    name: "专利复审程序",
    englishId: "patent-reexamination",
    children: [
      {
        name: "复审请求的提出",
        englishId: "reexamination-request",
        value: 1.0,
      },
      {
        name: "合议审查与复审决定",
        englishId: "collegial-review",
        value: 1.5,
      },
    ],
  },
  {
    name: "专利无效宣告",
    englishId: "patent-invalidation",
    children: [
      {
        name: "无效宣告理由",
        englishId: "invalidation-grounds",
        value: 1.5,
      },
      {
        name: "口头审理程序",
        englishId: "oral-proceeding",
        value: 1.0,
      },
    ],
  },
  {
    name: "专利权保护",
    englishId: "patent-rights-protection",
    children: [
      {
        name: "专利权保护范围",
        englishId: "protection-scope",
        children: [
          {
            name: "等同原则",
            englishId: "doctrine-of-equivalents",
            value: 1.0,
          },
          {
            name: "权利要求解释规则",
            englishId: "claim-interpretation",
            value: 0.5,
          },
        ],
      },
      {
        name: "专利侵权行为类型",
        englishId: "infringement-types",
        value: 1.0,
      },
      {
        name: "侵权抗辩事由",
        englishId: "infringement-defenses",
        children: [
          {
            name: "Bolar例外",
            englishId: "bolar-exemption",
            value: 0.5,
          },
          {
            name: "先用权",
            englishId: "prior-use-right",
            value: 0.5,
          },
        ],
      },
      {
        name: "侵权救济",
        englishId: "remedies",
        value: 1.5,
      },
    ],
  },
  {
    name: "专利代理实务",
    englishId: "patent-agency-practice",
    children: [
      {
        name: "权利要求撰写实务",
        englishId: "claims-drafting-advanced",
        value: 3.0,
      },
      {
        name: "审查意见答复实务",
        englishId: "oa-response-practice",
        value: 2.5,
      },
      {
        name: "无效宣告实务",
        englishId: "invalidation-practice",
        value: 2.5,
      },
    ],
  },
  {
    name: "相关法律知识",
    englishId: "related-laws",
    children: [
      {
        name: "民法基础",
        englishId: "civil-law-basics",
        value: 1.0,
      },
      {
        name: "技术合同法",
        englishId: "contract-law-tech",
        value: 1.0,
      },
      {
        name: "行政法与行政诉讼",
        englishId: "administrative-procedure",
        value: 1.0,
      },
      {
        name: "民事诉讼程序",
        englishId: "civil-procedure",
        value: 0.5,
      },
      {
        name: "TRIPS协定",
        englishId: "trips-agreement",
        value: 0.5,
      },
    ],
  },
  {
    name: "PCT国际申请",
    englishId: "pct-system",
    children: [
      {
        name: "PCT国际申请程序",
        englishId: "pct-filing",
        value: 1.0,
      },
      {
        name: "PCT国家阶段",
        englishId: "pct-national-phase",
        value: 1.0,
      },
    ],
  },
];
