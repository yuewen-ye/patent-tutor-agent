import { Outlet, useLocation } from "react-router-dom";
import { Header } from "./Header";
import { ChatFloatingButton } from "@/components/chat/ChatFloatingButton";

export function RootLayout() {
  const location = useLocation();
  const isFullscreen = location.pathname.startsWith("/session/") || location.pathname.startsWith("/course/") || location.pathname.startsWith("/feedback/");
  const hideFloatingChat = location.pathname === "/onboarding";

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">
      <Header />
      <main className={`flex-1 min-h-0 ${isFullscreen ? "overflow-hidden" : "overflow-y-auto"}`}>
        <Outlet />
      </main>
      {!isFullscreen && (
        <footer className="border-t border-border/60 py-3 text-center text-xs text-muted-foreground flex-shrink-0">
          <p>Patent Tutor Agent · 多智能体协同专利导学系统</p>
        </footer>
      )}
      {!hideFloatingChat && <ChatFloatingButton />}
    </div>
  );
}