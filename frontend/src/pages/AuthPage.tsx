import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Eye, EyeOff, User, Lock, Mail, UserPlus, LogIn } from "lucide-react";
import { authApi, saveAuth } from "@/api/auth";
import { ApiError } from "@/api/client";

type AuthMode = "login" | "register";

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

  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
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
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-background via-secondary/30 to-accent/30">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-primary/10 mb-4">
            <User className="w-8 h-8 text-primary" />
          </div>
          <h1 className="text-2xl font-semibold text-foreground mb-2">
            专利智能导学系统
          </h1>
          <p className="text-sm text-muted-foreground">
            {mode === "login" ? "欢迎回来，请登录您的账号" : "创建新账号，开始学习之旅"}
          </p>
        </div>

        <Card className="border-border/40 bg-card/90 shadow-elevated backdrop-blur-sm">
          <CardHeader className="pb-4">
            <div className="flex items-center justify-center gap-4">
              <button
                onClick={() => {
                  setMode("login");
                  setError("");
                }}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  mode === "login"
                    ? "bg-primary text-primary-foreground shadow-soft"
                    : "text-muted-foreground hover:bg-secondary/50"
                }`}
              >
                <LogIn className="w-4 h-4" />
                登录
              </button>
              <button
                onClick={() => {
                  setMode("register");
                  setError("");
                }}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  mode === "register"
                    ? "bg-primary text-primary-foreground shadow-soft"
                    : "text-muted-foreground hover:bg-secondary/50"
                }`}
              >
                <UserPlus className="w-4 h-4" />
                注册
              </button>
            </div>
          </CardHeader>

          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-5">
              {error && (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
                  <Badge variant="outline" className="text-xs h-5 px-2">
                    提示
                  </Badge>
                  <span>{error}</span>
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="login_id" className="flex items-center gap-2">
                  <User className="w-3.5 h-3.5 text-muted-foreground" />
                  登录账号 <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="login_id"
                  placeholder="请输入登录账号"
                  value={formData.login_id}
                  onChange={(e) => handleInputChange("login_id", e.target.value)}
                  className="h-11"
                  disabled={loading}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="password" className="flex items-center gap-2">
                  <Lock className="w-3.5 h-3.5 text-muted-foreground" />
                  密码 <span className="text-destructive">*</span>
                </Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="请输入密码（至少6位）"
                    value={formData.password}
                    onChange={(e) => handleInputChange("password", e.target.value)}
                    className="h-11 pr-10"
                    disabled={loading}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {showPassword ? (
                      <EyeOff className="w-4 h-4" />
                    ) : (
                      <Eye className="w-4 h-4" />
                    )}
                  </button>
                </div>
                {mode === "login" && (
                  <p className="text-xs text-muted-foreground text-right">
                    忘记密码？
                  </p>
                )}
              </div>

              {mode === "register" && (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="display_name" className="flex items-center gap-2">
                      <User className="w-3.5 h-3.5 text-muted-foreground" />
                      显示名称
                    </Label>
                    <Input
                      id="display_name"
                      placeholder="请输入您的名字（可选）"
                      value={formData.display_name}
                      onChange={(e) => handleInputChange("display_name", e.target.value)}
                      className="h-11"
                      disabled={loading}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="email" className="flex items-center gap-2">
                      <Mail className="w-3.5 h-3.5 text-muted-foreground" />
                      邮箱
                    </Label>
                    <Input
                      id="email"
                      type="email"
                      placeholder="请输入您的邮箱（可选）"
                      value={formData.email}
                      onChange={(e) => handleInputChange("email", e.target.value)}
                      className="h-11"
                      disabled={loading}
                    />
                  </div>
                </>
              )}

              <Button
                type="submit"
                className="w-full h-12 text-base"
                disabled={loading || !formData.login_id || !formData.password}
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    {mode === "login" ? "登录中..." : "注册中..."}
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    {mode === "login" ? (
                      <>
                        <LogIn className="w-4 h-4" />
                        登录
                      </>
                    ) : (
                      <>
                        <UserPlus className="w-4 h-4" />
                        注册
                      </>
                    )}
                  </span>
                )}
              </Button>
            </form>
          </CardContent>

          <div className="px-6 pb-6">
            <p className="text-center text-xs text-muted-foreground">
              登录即表示您同意我们的服务条款和隐私政策
            </p>
          </div>
        </Card>
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