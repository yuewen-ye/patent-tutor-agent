import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { sessionsApi } from "@/api/sessions";
import { CourseResourceTabs } from "@/components/course/CourseResourceTabs";
import { LearnerProfileCard } from "@/components/profile/LearnerProfileCard";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Loader2, ArrowLeft } from "lucide-react";
import { PixelMascot } from "@/components/auth/PixelMascot";

export function CoursePage() {
  const { sessionId } = useParams<{ sessionId: string }>();

  const { data: session, isLoading } = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => sessionsApi.get(sessionId!),
    enabled: !!sessionId,
  });

  const state = session?.state;

  return (
    <div className="container py-8 md:py-10">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" asChild className="mr-2 h-9 w-9">
                <Link to={`/session/${sessionId}`}>
                  <ArrowLeft className="h-5 w-5" />
                </Link>
              </Button>
              <div className="flex items-center gap-3">
                <PixelMascot size={36} />
                <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-[#C15B27]">课程学习</h1>
                <StatusBadge status={session?.status} />
              </div>
            </div>
          </div>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center gap-2 text-muted-foreground py-16">
            <Loader2 className="h-5 w-5 animate-spin" />
            加载课程...
          </div>
        )}

        {session && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            <div className="lg:col-span-2 space-y-5">
              <CourseResourceTabs
                sessionId={sessionId!}
                coursePackage={state?.course_package}
                artifacts={state?.artifacts || []}
                sessionStatus={session?.status}
              />
            </div>

            <div className="space-y-5">
              <LearnerProfileCard profile={state?.learner_profile} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}