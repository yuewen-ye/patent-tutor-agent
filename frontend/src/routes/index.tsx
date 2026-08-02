import { createBrowserRouter, Navigate } from "react-router-dom";
import { RootLayout } from "@/components/layout/RootLayout";
import { HomePage } from "@/pages/HomePage";
import { OnboardingPage } from "@/pages/OnboardingPage";
import { SessionPage } from "@/pages/SessionPage";
import { CoursePage } from "@/pages/CoursePage";
import { FeedbackPage } from "@/pages/FeedbackPage";
import { LearnerPage } from "@/pages/LearnerPage";
import { SessionsPage } from "@/pages/SessionsPage";
import { ChatPage } from "@/pages/ChatPage";
import { AuthPage } from "@/pages/AuthPage";
import { HistoryCoursesPage } from "@/pages/HistoryCoursesPage";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { isAuthenticated } from "@/api/auth";

function HomeRedirect() {
  if (!isAuthenticated()) {
    return <Navigate to="/auth" replace />;
  }
  return <HomePage />;
}

export const router = createBrowserRouter([
  {
    path: "/auth",
    element: <AuthPage />,
  },
  {
    path: "/",
    element: <RootLayout />,
    children: [
      { index: true, element: <HomeRedirect /> },
      { path: "onboarding", element: <ProtectedRoute><OnboardingPage /></ProtectedRoute> },
      { path: "session/:sessionId", element: <ProtectedRoute><SessionPage /></ProtectedRoute> },
      { path: "course/:sessionId", element: <ProtectedRoute><CoursePage /></ProtectedRoute> },
      { path: "feedback/:sessionId", element: <ProtectedRoute><FeedbackPage /></ProtectedRoute> },
      { path: "learner", element: <ProtectedRoute><LearnerPage /></ProtectedRoute> },
      { path: "sessions", element: <ProtectedRoute><SessionsPage /></ProtectedRoute> },
      { path: "chat", element: <ProtectedRoute><ChatPage /></ProtectedRoute> },
      { path: "courses", element: <ProtectedRoute><HistoryCoursesPage /></ProtectedRoute> },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
