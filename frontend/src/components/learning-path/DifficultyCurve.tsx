import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  Line,
  ComposedChart,
  Legend,
} from "recharts";
import { Clock, BookOpen } from "lucide-react";
import type { LearningPathItem } from "@/types";

interface DifficultyCurveProps {
  path: LearningPathItem[];
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value: number; dataKey: string; payload?: LearningPathItem & { step: number; difficulty: number } }>;
  label?: number;
}) {
  if (!active || !payload || !label) return null;

  const item = payload[0]?.payload as LearningPathItem & { step: number; difficulty: number };
  if (!item) return null;

  const difficulty = payload.find((p) => p.dataKey === "difficulty")?.value;
  const duration = payload.find((p) => p.dataKey === "duration")?.value;

  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3 shadow-xl min-w-[240px]">
      <div className="flex items-center gap-2 mb-2 pb-2 border-b border-border">
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary/10 text-primary text-xs font-bold">
          {label}
        </span>
        <span className="text-sm font-semibold">{item.node_name}</span>
      </div>

      <div className="space-y-1.5 text-xs">
        {difficulty !== undefined && (
          <div className="flex items-center justify-between gap-3">
            <span className="text-muted-foreground">难度</span>
            <span className="font-medium text-foreground">{difficulty} 级</span>
          </div>
        )}
        {duration !== undefined && (
          <div className="flex items-center justify-between gap-3">
            <span className="text-muted-foreground flex items-center gap-1">
              <Clock className="h-3 w-3" />
              时长
            </span>
            <span className="font-medium text-foreground">{duration} 分钟</span>
          </div>
        )}
        <div className="flex items-start justify-between gap-3">
          <span className="text-muted-foreground flex items-center gap-1 shrink-0">
            <BookOpen className="h-3 w-3 mt-0.5" />
            策略
          </span>
          <span className="text-foreground text-right">{item.strategy}</span>
        </div>
        <div className="flex items-start justify-between gap-3">
          <span className="text-muted-foreground shrink-0">前置</span>
          <span className="text-foreground text-right">
            {item.prerequisites && item.prerequisites.length > 0
              ? item.prerequisites.join(", ")
              : "无"}
          </span>
        </div>
      </div>
    </div>
  );
}

export function DifficultyCurve({ path }: DifficultyCurveProps) {
  const data = path.map((item, index) => {
    const difficulty = Math.round((item.node_id.length % 10) * 10 + 20);
    return {
      step: index + 1,
      node_id: item.node_id,
      node_name: item.node_name,
      strategy: item.strategy,
      prerequisites: item.prerequisites,
      difficulty,
      difficultyArea: difficulty,
      duration: item.duration_min,
    };
  });

  return (
    <div className="h-[320px] w-full rounded-xl border border-border/30 bg-card/80 p-4">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 28 }}>
          <defs>
            <linearGradient id="difficultyGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#1f5f4f" stopOpacity={0.25} />
              <stop offset="95%" stopColor="#1f5f4f" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            dataKey="step"
            stroke="hsl(var(--muted-foreground))"
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
            label={{
              value: "学习进度（节点顺序）",
              position: "insideBottom",
              offset: -18,
              fill: "hsl(var(--muted-foreground))",
              fontSize: 12,
            }}
          />
          <YAxis
            yAxisId="left"
            stroke="hsl(var(--muted-foreground))"
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
            domain={[0, 100]}
            label={{
              value: "难度等级",
              angle: -90,
              position: "insideLeft",
              fill: "hsl(var(--muted-foreground))",
              fontSize: 12,
            }}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            stroke="hsl(var(--muted-foreground))"
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
            label={{
              value: "时长（分钟）",
              angle: 90,
              position: "insideRight",
              fill: "hsl(var(--muted-foreground))",
              fontSize: 12,
            }}
          />
          <Tooltip
            content={<CustomTooltip />}
            cursor={{ stroke: "hsl(var(--primary))", strokeWidth: 1, strokeDasharray: "4 4" }}
          />
          <Legend
            verticalAlign="top"
            height={36}
            iconType="plainline"
            formatter={(value: string) => (
              <span className="text-sm text-foreground/80">
                {value === "difficulty"
                  ? "难度等级（左轴）"
                  : value === "duration"
                    ? "学习时长（右轴）"
                    : ""}
              </span>
            )}
          />
          <Area
            yAxisId="left"
            type="monotone"
            dataKey="difficultyArea"
            stroke="none"
            fill="url(#difficultyGradient)"
            legendType="none"
          />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="difficulty"
            name="difficulty"
            stroke="hsl(var(--primary))"
            strokeWidth={2.5}
            dot={{ fill: "hsl(var(--primary))", strokeWidth: 0, r: 4 }}
            activeDot={{ r: 7, fill: "hsl(var(--primary))", stroke: "hsl(var(--card))", strokeWidth: 2 }}
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="duration"
            name="duration"
            stroke="#c69456"
            strokeWidth={2}
            strokeDasharray="5 5"
            dot={{ fill: "#c69456", strokeWidth: 0, r: 3 }}
            activeDot={{ r: 6, fill: "#c69456", stroke: "hsl(var(--card))", strokeWidth: 2 }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
