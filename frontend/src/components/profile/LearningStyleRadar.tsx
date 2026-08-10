import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Target } from "lucide-react";

interface LearningStyleRadarProps {
  learningStyle?: string;
}

const styleDimensions = [
  { key: "perception", label: "感知方式", options: ["sensing", "intuitive"] },
  { key: "input", label: "输入偏好", options: ["visual", "verbal"] },
  { key: "processing", label: "处理方式", options: ["active", "reflective"] },
  { key: "understanding", label: "理解方式", options: ["sequential", "global"] },
];

const optionLabels: Record<string, string> = {
  sensing: "具体型",
  intuitive: "直觉型",
  visual: "视觉型",
  verbal: "言语型",
  active: "实践型",
  reflective: "反思型",
  sequential: "顺序型",
  global: "整体型",
};

export function LearningStyleRadar({ learningStyle }: LearningStyleRadarProps) {
  if (!learningStyle) {
    return (
      <Card className="rounded-2xl border border-white/70 bg-white/90 shadow-soft h-full overflow-hidden">
        <CardContent className="py-8 text-center text-muted-foreground text-sm h-full flex items-center justify-center">
          暂无学习风格数据
        </CardContent>
      </Card>
    );
  }

  const scores = parseLearningStyle(learningStyle);
  const center = 50;
  const radius = 36;
  const labelRadius = 46;
  const levels = [0.2, 0.4, 0.6, 0.8, 1];

  const points = styleDimensions.map((dim, i) => {
    const angle = (Math.PI * 2 * i) / styleDimensions.length - Math.PI / 2;
    const value = scores[dim.key] || 0.5;
    const x = center + radius * Math.cos(angle) * value;
    const y = center + radius * Math.sin(angle) * value;
    const lx = center + labelRadius * Math.cos(angle);
    const ly = center + labelRadius * Math.sin(angle);
    return { x, y, lx, ly, label: dim.label, value, angle };
  });

  return (
    <Card className="rounded-2xl border border-white/70 bg-white/90 shadow-soft h-full overflow-hidden">
      <div className="h-1.5 w-full bg-gradient-to-r from-[#D9773E] via-[#F59E0B] to-[#C15B27]" />
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-medium flex items-center gap-2">
          <span className="inline-flex items-center justify-center rounded-lg bg-[#D9773E]/10 p-1.5 text-[#D9773E]">
            <Target className="h-4 w-4" />
          </span>
          学习风格分析
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-2">
        <div className="flex flex-col items-center">
          <svg
            viewBox="0 0 100 100"
            className="w-full max-w-[260px] h-auto overflow-visible"
            aria-label="学习风格雷达图"
          >
            <defs>
              <radialGradient id="radarFill" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#D9773E" stopOpacity="0.35" />
                <stop offset="100%" stopColor="#C15B27" stopOpacity="0.12" />
              </radialGradient>
            </defs>

            {/* 同心网格 */}
            {levels.map((scale) => {
              const levelPoints = styleDimensions
                .map((_, i) => {
                  const angle = (Math.PI * 2 * i) / styleDimensions.length - Math.PI / 2;
                  const x = center + radius * Math.cos(angle) * scale;
                  const y = center + radius * Math.sin(angle) * scale;
                  return `${x},${y}`;
                })
                .join(" ");
              return (
                <polygon
                  key={scale}
                  points={levelPoints}
                  fill="none"
                  stroke="rgba(193, 91, 39, 0.12)"
                  strokeWidth="0.5"
                />
              );
            })}

            {/* 轴线 */}
            {styleDimensions.map((dim, i) => {
              const angle = (Math.PI * 2 * i) / styleDimensions.length - Math.PI / 2;
              const x = center + radius * Math.cos(angle);
              const y = center + radius * Math.sin(angle);
              return (
                <line
                  key={dim.key}
                  x1={center}
                  y1={center}
                  x2={x}
                  y2={y}
                  stroke="rgba(193, 91, 39, 0.18)"
                  strokeWidth="0.5"
                />
              );
            })}

            {/* 数据区域 */}
            <polygon
              points={points.map((p) => `${p.x},${p.y}`).join(" ")}
              fill="url(#radarFill)"
              stroke="#C15B27"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />

            {/* 数据点 */}
            {points.map((p, i) => (
              <circle
                key={`point-${i}`}
                cx={p.x}
                cy={p.y}
                r="2.5"
                fill="#D9773E"
                stroke="#fff"
                strokeWidth="0.8"
              />
            ))}

            {/* 维度标签 */}
            {points.map((p, i) => (
              <text
                key={`label-${i}`}
                x={p.lx}
                y={p.ly}
                textAnchor="middle"
                dominantBaseline="middle"
                fontSize="4"
                fontWeight="500"
                fill="#8B5A3C"
              >
                {p.label}
              </text>
            ))}
          </svg>

          <div className="grid grid-cols-2 gap-3 mt-6 w-full">
            {styleDimensions.map((dim) => {
              const value = scores[dim.key] || 0.5;
              const dominant = value > 0.5 ? dim.options[1] : dim.options[0];
              return (
                <div
                  key={dim.key}
                  className="flex items-center justify-between rounded-xl border border-[#FFE8D0]/80 bg-[#FFF7ED]/70 px-3 py-2.5"
                >
                  <span className="text-xs text-[#8B5A3C]">{dim.label}</span>
                  <span className="text-sm font-semibold text-[#C15B27]">
                    {optionLabels[dominant] || dominant}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function parseLearningStyle(style: string): Record<string, number> {
  const result: Record<string, number> = {};
  const lowerStyle = style.toLowerCase();

  result.perception = lowerStyle.includes("sensing") || lowerStyle.includes("具体") || lowerStyle.includes("案例") ? 0.7 : 0.3;
  result.perception = lowerStyle.includes("intuitive") || lowerStyle.includes("抽象") || lowerStyle.includes("理论") ? 0.7 : result.perception;

  result.input = lowerStyle.includes("visual") || lowerStyle.includes("图表") || lowerStyle.includes("流程") ? 0.7 : 0.3;
  result.input = lowerStyle.includes("verbal") || lowerStyle.includes("文字") || lowerStyle.includes("讲解") ? 0.7 : result.input;

  result.processing = lowerStyle.includes("active") || lowerStyle.includes("实践") || lowerStyle.includes("练习") ? 0.7 : 0.3;
  result.processing = lowerStyle.includes("reflective") || lowerStyle.includes("思考") || lowerStyle.includes("理解") ? 0.7 : result.processing;

  result.understanding = lowerStyle.includes("sequential") || lowerStyle.includes("线性") || lowerStyle.includes("步骤") ? 0.7 : 0.3;
  result.understanding = lowerStyle.includes("global") || lowerStyle.includes("全局") || lowerStyle.includes("整体") ? 0.7 : result.understanding;

  return result;
}
