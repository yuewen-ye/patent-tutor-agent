import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  Line,
  ComposedChart,
} from "recharts";
import type { LearningPathItem } from "@/types";

interface DifficultyCurveProps {
  path: LearningPathItem[];
}

export function DifficultyCurve({ path }: DifficultyCurveProps) {
  const data = path.map((item, index) => ({
    step: index + 1,
    name: item.node_name,
    difficulty: Math.round((item.node_id.length % 10) * 10 + 20), // Placeholder since no difficulty field in LearningPathItem
    duration: item.duration_min,
  }));

  return (
    <div className="h-[300px] w-full rounded-xl border border-white/5 bg-slate-950/40 p-4">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="difficultyGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#22d3ee" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="step" stroke="#64748b" tick={{ fill: "#94a3b8", fontSize: 12 }} />
          <YAxis
            yAxisId="left"
            stroke="#64748b"
            tick={{ fill: "#94a3b8", fontSize: 12 }}
            domain={[0, 100]}
            label={{ value: "难度", angle: -90, position: "insideLeft", fill: "#94a3b8" }}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            stroke="#64748b"
            tick={{ fill: "#94a3b8", fontSize: 12 }}
            label={{ value: "时长(分)", angle: 90, position: "insideRight", fill: "#94a3b8" }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#0f172a",
              border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: "8px",
            }}
            labelStyle={{ color: "#22d3ee" }}
            itemStyle={{ color: "#e2e8f0" }}
          />
          <Area
            yAxisId="left"
            type="monotone"
            dataKey="difficulty"
            stroke="none"
            fill="url(#difficultyGradient)"
          />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="difficulty"
            stroke="#22d3ee"
            strokeWidth={2}
            dot={{ fill: "#22d3ee", strokeWidth: 0, r: 4 }}
            activeDot={{ r: 6, fill: "#fbbf24" }}
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="duration"
            stroke="#fbbf24"
            strokeWidth={2}
            strokeDasharray="5 5"
            dot={{ fill: "#fbbf24", strokeWidth: 0, r: 3 }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
