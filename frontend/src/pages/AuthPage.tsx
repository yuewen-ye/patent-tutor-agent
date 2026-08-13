import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Eye,
  EyeOff,
  User,
  Lock,
  Mail,
  UserPlus,
  LogIn,
  Brain,
  BookOpen,
  MessageSquare,
  GraduationCap,
} from "lucide-react";
import { authApi, saveAuth } from "@/api/auth";
import { ApiError } from "@/api/client";
import { PixelMascot } from "@/components/auth/PixelMascot";
import { VideoBackground } from "@/components/auth/VideoBackground";

type AuthMode = "login" | "register";

const FEATURES = [
  {
    icon: Brain,
    title: "BKT 掌握度",
    desc: "实时建模知识掌握情况",
  },
  {
    icon: GraduationCap,
    title: "自评诊断",
    desc: "自适应评估薄弱知识点",
  },
  {
    icon: BookOpen,
    title: "双专家课程",
    desc: "多 Agent 协同生成讲义",
  },
  {
    icon: MessageSquare,
    title: "RAG 问答",
    desc: "法条案例秒级检索",
  },
];

/** Public URL of the login/register background video.
 *  Place the video file at frontend/public/auth-bg.mp4.
 */
const BACKGROUND_VIDEO_URL = "/auth-bg.mp4";

export function AuthPage() {
  const [mode, setMode] = useState<AuthMode>("login");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");

  const [formData, setFormData] = useState({
    login_id: "",
    password: "",
    display_name: "",
    email: "",
  });
  const [loginIdError, setLoginIdError] = useState<string>("");

  const navigate = useNavigate();

  const validateLoginId = (value: string) => {
    if (mode !== "register") return "";
    if (value.length > 0 && value.length < 3) {
      return "用户名至少需要 3 位字符";
    }
    return "";
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (mode === "register" && formData.login_id.length < 3) {
      setLoginIdError("用户名至少需要 3 位字符");
      return;
    }

    setLoading(true);

    try {
      if (mode === "login") {
        const data = await authApi.login({
          login_id: formData.login_id,
          password: formData.password,
        });
        saveAuth(data);
        navigate("/");
      } else {
        await authApi.register({
          login_id: formData.login_id,
          password: formData.password,
          display_name: formData.display_name || undefined,
          email: formData.email || undefined,
        });
        setMode("login");
        setError("注册成功，请登录");
      }
    } catch (err) {
      setError(resolveAuthError(err, mode));
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (field === "login_id") {
      setLoginIdError(validateLoginId(value));
    }
  };

  return (
    <div className="relative min-h-screen w-full overflow-hidden text-[#5C3A26]">
      {/* Full-screen background video. Falls back to the SVG desk scene if the video fails to load. */}
      <VideoBackground src={BACKGROUND_VIDEO_URL} className="z-0" />

      {/* Left-side login/register panel. The right side remains unobstructed so the video scene is visible. */}
      <div className="relative z-10 flex min-h-screen w-full">
        <div className="flex w-full flex-col justify-center bg-gradient-to-r from-[#FFF7ED]/85 via-[#FFF7ED]/40 to-transparent p-4 sm:p-8 lg:w-[48%] xl:w-[44%] lg:from-transparent lg:via-transparent lg:to-transparent lg:p-10 xl:p-12">
          {/* Mobile header */}
          <div className="mb-6 flex items-center gap-3 lg:hidden">
            <PixelMascot size={40} />
            <div>
              <h1 className="text-xl font-bold text-[#C15B27]">Patent Tutor Agent</h1>
              <p className="text-xs text-[#8B5A3C]">专利智能导学系统</p>
            </div>
          </div>

          <div className="w-full max-w-lg lg:mx-0">
            {/* Large display title above the login/register card. */}
            <div className="mb-8 hidden text-center lg:block">
              <h1 className="font-display text-4xl font-bold leading-tight tracking-tight text-[#D9773E] drop-shadow-sm xl:text-5xl">
                Patent Tutor agent
              </h1>
            </div>

            <div className="text-center lg:hidden">
              <p className="mb-6 text-sm text-[#8B5A3C]">
                {mode === "login"
                  ? "欢迎回来，继续你的专利学习之旅"
                  : "创建新账号，开启专利学习"}
              </p>
            </div>

            <div className="auth-theme">
              <Card className="border border-white/70 bg-white/90 shadow-[0_20px_60px_-15px_rgba(193,91,39,0.25)] backdrop-blur-xl">
                <CardHeader className="pb-4">
                  <div className="flex items-center justify-center gap-3">
                    <button
                      onClick={() => {
                        setMode("login");
                        setError("");
                        setLoginIdError("");
                      }}
                      className={`flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold transition-all ${
                        mode === "login"
                          ? "bg-[#D9773E] text-white shadow-md"
                          : "text-[#8B5A3C] hover:bg-[#D9773E]/10"
                      }`}
                    >
                      <LogIn className="h-4 w-4" />
                      登录
                    </button>
                    <button
                      onClick={() => {
                        setMode("register");
                        setError("");
                        setLoginIdError("");
                      }}
                      className={`flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold transition-all ${
                        mode === "register"
                          ? "bg-[#D9773E] text-white shadow-md"
                          : "text-[#8B5A3C] hover:bg-[#D9773E]/10"
                      }`}
                    >
                      <UserPlus className="h-4 w-4" />
                      注册
                    </button>
                  </div>
                </CardHeader>

                <CardContent>
                  <form onSubmit={handleSubmit} className="space-y-5">
                    {error && (
                      <div className="flex items-center gap-2 rounded-xl bg-[#D9773E]/10 p-3 text-sm text-[#9A4A1C]">
                        <Badge
                          variant="outline"
                          className="h-5 border-[#D9773E]/30 px-2 text-xs text-[#D9773E]"
                        >
                          提示
                        </Badge>
                        <span>{error}</span>
                      </div>
                    )}

                    <div className="space-y-2">
                      <Label
                        htmlFor="login_id"
                        className="flex items-center gap-2 text-[#5C3A26]"
                      >
                        <User className="h-3.5 w-3.5 text-[#9A6A4A]" />
                        登录账号 <span className="text-[#D9773E]">*</span>
                      </Label>
                      <Input
                        id="login_id"
                        placeholder="请输入登录账号"
                        value={formData.login_id}
                        onChange={(e) => handleInputChange("login_id", e.target.value)}
                        className={`h-11 border-[#E5C9AB] bg-white/80 placeholder:text-[#B8957A] focus-visible:ring-[#D9773E] ${
                          loginIdError ? "border-red-400 focus-visible:ring-red-400" : ""
                        }`}
                        disabled={loading}
                      />
                      {mode === "register" && (
                        <p
                          className={`text-xs ${
                            loginIdError
                              ? "text-red-600"
                              : "text-[#9A6A4A]"
                          }`}
                        >
                          {loginIdError || "用户名至少需要 3 位字符"}
                        </p>
                      )}
                    </div>

                    <div className="space-y-2">
                      <Label
                        htmlFor="password"
                        className="flex items-center gap-2 text-[#5C3A26]"
                      >
                        <Lock className="h-3.5 w-3.5 text-[#9A6A4A]" />
                        密码 <span className="text-[#D9773E]">*</span>
                      </Label>
                      <div className="relative">
                        <Input
                          id="password"
                          type={showPassword ? "text" : "password"}
                          placeholder="请输入密码（至少6位）"
                          value={formData.password}
                          onChange={(e) => handleInputChange("password", e.target.value)}
                          className="h-11 border-[#E5C9AB] bg-white/80 pr-10 placeholder:text-[#B8957A] focus-visible:ring-[#D9773E]"
                          disabled={loading}
                        />
                        <button
                          type="button"
                          onClick={() => setShowPassword(!showPassword)}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-[#9A6A4A] transition-colors hover:text-[#5C3A26]"
                        >
                          {showPassword ? (
                            <EyeOff className="h-4 w-4" />
                          ) : (
                            <Eye className="h-4 w-4" />
                          )}
                        </button>
                      </div>
                      {mode === "login" && (
                        <p className="cursor-pointer text-right text-xs text-[#9A6A4A] hover:text-[#D9773E]">
                          忘记密码？
                        </p>
                      )}
                    </div>

                    {mode === "register" && (
                      <>
                        <div className="space-y-2">
                          <Label
                            htmlFor="display_name"
                            className="flex items-center gap-2 text-[#5C3A26]"
                          >
                            <User className="h-3.5 w-3.5 text-[#9A6A4A]" />
                            显示名称
                          </Label>
                          <Input
                            id="display_name"
                            placeholder="请输入您的名字（可选）"
                            value={formData.display_name}
                            onChange={(e) =>
                              handleInputChange("display_name", e.target.value)
                            }
                            className="h-11 border-[#E5C9AB] bg-white/80 placeholder:text-[#B8957A] focus-visible:ring-[#D9773E]"
                            disabled={loading}
                          />
                        </div>

                        <div className="space-y-2">
                          <Label
                            htmlFor="email"
                            className="flex items-center gap-2 text-[#5C3A26]"
                          >
                            <Mail className="h-3.5 w-3.5 text-[#9A6A4A]" />
                            邮箱
                          </Label>
                          <Input
                            id="email"
                            type="email"
                            placeholder="请输入您的邮箱（可选）"
                            value={formData.email}
                            onChange={(e) => handleInputChange("email", e.target.value)}
                            className="h-11 border-[#E5C9AB] bg-white/80 placeholder:text-[#B8957A] focus-visible:ring-[#D9773E]"
                            disabled={loading}
                          />
                        </div>
                      </>
                    )}

                    <Button
                      type="submit"
                      className="h-12 w-full text-base"
                      disabled={
                        loading ||
                        !formData.login_id ||
                        !formData.password ||
                        (mode === "register" && formData.login_id.length < 3)
                      }
                    >
                      {loading ? (
                        <span className="flex items-center gap-2">
                          <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                          {mode === "login" ? "登录中..." : "注册中..."}
                        </span>
                      ) : (
                        <span className="flex items-center gap-2">
                          {mode === "login" ? (
                            <>
                              <LogIn className="h-4 w-4" />
                              登录
                            </>
                          ) : (
                            <>
                              <UserPlus className="h-4 w-4" />
                              注册
                            </>
                          )}
                        </span>
                      )}
                    </Button>
                  </form>
                </CardContent>

                <div className="px-6 pb-6">
                  <p className="text-center text-xs text-[#9A6A4A]">
                    登录即表示您同意我们的服务条款和隐私政策
                  </p>
                </div>
              </Card>
            </div>
          </div>

          {/* Feature cards below the login/register card. */}
          <div className="mt-6 grid w-full max-w-lg grid-cols-2 gap-3">
            {FEATURES.map((feature) => {
              const Icon = feature.icon;
              return (
                <div
                  key={feature.title}
                  className="flex items-center gap-3 rounded-2xl border border-white/60 bg-white/80 p-3 shadow-soft backdrop-blur-sm transition-transform hover:-translate-y-0.5"
                >
                  <div className="inline-flex shrink-0 rounded-xl bg-[#D9773E]/10 p-2 text-[#D9773E]">
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0">
                    <div className="text-xs font-semibold text-[#7C3A1C]">
                      {feature.title}
                    </div>
                    <div className="truncate text-[10px] text-[#9A6A4A]">
                      {feature.desc}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right spacer keeps the video scene fully visible on large screens. */}
        <div className="hidden lg:block lg:flex-1" />
      </div>
    </div>
  );
}

const REASON_MESSAGES: Record<string, string> = {
  login_id_not_found: "用户不存在",
  password_incorrect: "密码错误",
  account_disabled: "账号已被禁用",
  login_id_already_exists: "登录账号已存在",
  email_already_exists: "邮箱已被注册",
};

function resolveAuthError(err: unknown, mode: AuthMode): string {
  if (err instanceof ApiError && err.body) {
    const detail = (err.body as { detail?: unknown }).detail;
    if (detail && typeof detail === "object") {
      const reason = String((detail as { reason?: unknown }).reason ?? "");
      if (reason && REASON_MESSAGES[reason]) {
        return REASON_MESSAGES[reason];
      }
    }
  }
  if (err instanceof Error && err.message) {
    return err.message;
  }
  return mode === "login" ? "登录失败，请重试" : "注册失败，请重试";
}
