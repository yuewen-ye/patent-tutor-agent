import { useQuery } from "@tanstack/react-query";
import { artifactsApi } from "@/api/artifacts";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2 } from "lucide-react";

interface ArtifactViewerProps {
  sessionId: string;
  artifactPath: string;
  title?: string;
}

export function ArtifactViewer({ sessionId, artifactPath, title }: ArtifactViewerProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["artifact", sessionId, artifactPath],
    queryFn: () => artifactsApi.getArtifact(sessionId, artifactPath),
    enabled: !!sessionId && !!artifactPath,
  });

  return (
    <Card className="border-white/5 bg-card/50">
      {title && (
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-medium text-cyan-200/90">{title}</CardTitle>
        </CardHeader>
      )}
      <CardContent>
        <div className="max-h-[calc(100vh-320px)] overflow-y-auto pr-1">
          {isLoading && (
            <div className="flex items-center gap-2 text-muted-foreground py-8">
              <Loader2 className="h-4 w-4 animate-spin" />
              加载产物中...
            </div>
          )}
          {error && (
            <div className="text-destructive py-4">
              读取产物失败：{error instanceof Error ? error.message : String(error)}
            </div>
          )}
          {data && <MarkdownRenderer content={data} />}
        </div>
      </CardContent>
    </Card>
  );
}
