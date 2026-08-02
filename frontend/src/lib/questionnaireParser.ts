export interface Question {
  question_id: string;
  question: string;
  type: "choice" | "open";
  options?: Array<{ key: string; text: string }>;
  subsection?: string;
}

export interface QuestionGroup {
  title: string;
  questions: Question[];
}

const EXCLUDED_SECTIONS = ["学员模拟作答记录", "评分说明"];

export function parseQuestionnaireGroups(markdown: string): QuestionGroup[] {
  const groups: QuestionGroup[] = [];
  
  const sections = markdown.split(/^##\s+/m);
  
  for (const section of sections) {
    if (!section.trim()) continue;
    
    const lines = section.split("\n");
    const titleLine = lines[0].trim();
    const title = titleLine.replace(/^[一二三四五六七八九十]、/, "").trim();
    
    if (EXCLUDED_SECTIONS.some((s) => title.includes(s))) continue;
    
    const group: QuestionGroup = { title, questions: [] };
    
    let currentSubsection = "";
    let questionBuffer: string[] = [];
    
    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();
      
      if (line.startsWith("### ")) {
        if (questionBuffer.length > 0) {
          parseQuestionBlock(group, questionBuffer.join("\n"), currentSubsection);
        }
        currentSubsection = line.slice(4).trim();
        questionBuffer = [];
        continue;
      }
      
      if (line.startsWith("---") || line.startsWith("==========")) {
        if (questionBuffer.length > 0) {
          parseQuestionBlock(group, questionBuffer.join("\n"), currentSubsection);
        }
        questionBuffer = [];
        continue;
      }
      
      const qMatch = line.match(/^\*\*(Q\d+)\*\*/);
      if (qMatch) {
        if (questionBuffer.length > 0) {
          parseQuestionBlock(group, questionBuffer.join("\n"), currentSubsection);
        }
        questionBuffer = [line];
        continue;
      }
      
      if (questionBuffer.length > 0) {
        questionBuffer.push(line);
      }
    }
    
    if (questionBuffer.length > 0) {
      parseQuestionBlock(group, questionBuffer.join("\n"), currentSubsection);
    }
    
    if (group.questions.length > 0) {
      groups.push(group);
    }
  }
  
  return groups;
}

function parseQuestionBlock(
  group: QuestionGroup,
  block: string,
  subsection: string
): void {
  const qMatch = block.match(/^\*\*(Q\d+)\*\*\s*(.+)/);
  if (!qMatch) return;
  
  const questionId = qMatch[1];
  let questionText = qMatch[2].trim();
  
  const options = extractAllOptions(block);
  
  if (options.length >= 2) {
    for (const opt of options) {
      questionText = questionText.replace(
        new RegExp(`${opt.key}\\.\\s*${escapeRegExp(opt.text)}`, "gi"),
        ""
      ).trim();
    }
    
    group.questions.push({
      question_id: questionId,
      question: questionText || "请回答此问题",
      type: "choice",
      options: options.sort((a, b) => a.key.localeCompare(b.key)),
      subsection: subsection || undefined,
    });
  } else {
    group.questions.push({
      question_id: questionId,
      question: questionText || "请回答此问题",
      type: "open",
      subsection: subsection || undefined,
    });
  }
}

function extractAllOptions(block: string): Array<{ key: string; text: string }> {
  const options: Array<{ key: string; text: string }> = [];
  const optionKeys = ["A", "B", "C", "D"];
  
  for (const key of optionKeys) {
    const regex = new RegExp(`${key}\\.\\s*([\\s\\S]+?)(?=\\s*[A-D]\\.|$)`, "g");
    let match;
    let fullText = "";
    
    while ((match = regex.exec(block)) !== null) {
      fullText += " " + match[1].trim();
    }
    
    fullText = fullText.trim().replace(/\s+/g, " ");
    fullText = fullText.replace(/^\s*---+\s*/, "").replace(/\s*---+\s*$/, "");
    
    if (fullText.length > 0) {
      options.push({ key, text: fullText });
    }
  }
  
  return options;
}

function escapeRegExp(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}