import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface LearningStyleRadarProps {
  learningStyle?: string;
}

const styleDimensions = [
  { key: "perception", label: "感知方式", options: ["sensing", "intuitive"] },
  { key: "input", label: "输入偏好", options: ["visual", "verbal"] },
  { key: "processing", label: "处理方式", options: ["active", "reflective"] },
  { key: "understanding", label: "理解方式", options: ["sequential", "global"] },
];

export function LearningStyleRadar({ learningStyle }: LearningStyleRadarProps) {
  if (!learningStyle) {
    return (
      <Card className="border-border/40 bg-card shadow-soft">
        <CardContent className="py-8 text-center text-muted-foreground text-sm">
          暂无学习风格数据
        </CardContent>
      </Card>
    );
  }

  const scores = parseLearningStyle(learningStyle);
  const points = styleDimensions.map((dim, i) => {
    const angle = (Math.PI * 2 * i) / styleDimensions.length - Math.PI / 2;
    const value = scores[dim.key] || 0.5;
    const x = 50 + 35 * Math.cos(angle) * value;
    const y = 50 + 35 * Math.sin(angle) * value;
    return { x, y, label: dim.label, value };
  });

  return (
    <Card className="border-border/40 bg-card shadow-soft">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-medium">学习风格分析</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col items-center">
          <svg viewBox="0 0 100 100" className="w-full max-w-[200px] h-auto">
            {[0.25, 0.5, 0.75, 1].map((scale) => (
              <polygon
                key={scale}
                points={styleDimensions
                  .map((_, i) => {
                    const angle = (Math.PI * 2 * i) / styleDimensions.length - Math.PI / 2;
                    const x = 50 + 35 * Math.cos(angle) * scale;
                    const y = 50 + 35 * Math.sin(angle) * scale;
                    return `${x},${y}`;
                  })
                  .join(" ")}
                fill="none"
                stroke="rgba(148, 163, 184, 0.2)"
                strokeWidth="0.5"
              />
            ))}
            {styleDimensions.map((dim, i) => {
              const angle = (Math.PI * 2 * i) / styleDimensions.length - Math.PI / 2;
              return (
                <line
                  key={dim.key}
                  x1="50"
                  y1="50"
                  x2={50 + 35 * Math.cos(angle)}
                  y2={50 + 35 * Math.sin(angle)}
                  stroke="rgba(148, 163, 184, 0.3)"
                  strokeWidth="0.5"
                />
              );
            })}
            <polygon
              points={points.map((p) => `${p.x},${p.y}`).join(" ")}
              fill="rgba(99, 102, 241, 0.2)"
              stroke="rgba(99, 102, 241, 0.6)"
              strokeWidth="1.5"
            />
            {points.map((p, i) => (
              <circle
                key={i}
                cx={p.x}
                cy={p.y}
                r="2"
                fill="rgba(99, 102, 241, 0.8)"
              />
            ))}
          </svg>
          <div className="grid grid-cols-2 gap-3 mt-4 w-full max-w-[200px]">
            {styleDimensions.map((dim) => (
              <div key={dim.key} className="text-center">
                <div className="text-xs text-muted-foreground">{dim.label}</div>
                <div className="text-sm font-medium text-foreground">
                  {scores[dim.key] > 0.5 ? dim.options[1] : dim.options[0]}
                </div>
              </div>
            ))}
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
