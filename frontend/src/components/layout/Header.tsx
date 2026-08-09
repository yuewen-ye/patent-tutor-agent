import { Link, useLocation, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Home, MessageSquare, FileText, Users, Menu, X, LogIn, LogOut, User } from "lucide-react";
import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { getAuth, clearAuth } from "@/api/auth";
import { PixelMascot } from "@/components/auth/PixelMascot";
import type { AuthResponse } from "@/api/auth";

const navItems = [
  { href: "/", label: "首页", icon: Home },
  { href: "/onboarding", label: "自评诊断", icon: FileText },
  { href: "/sessions", label: "会话管理", icon: MessageSquare },
  { href: "/learner", label: "学员中心", icon: Users },
];

export function Header() {
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [auth, setAuth] = useState<AuthResponse | null>(null);

  useEffect(() => {
    setAuth(getAuth());
  }, []);

  const handleLogout = () => {
    clearAuth();
    setAuth(null);
    navigate("/auth");
  };

  const isActive = (href: string) => {
    if (href === "/") return location.pathname === "/";
    if (href.startsWith("/learner")) return location.pathname.startsWith("/learner");
    return location.pathname === href;
  };

  return (
    <header className="sticky top-0 z-50 border-b border-white/70 bg-[#FFF7ED]/90 backdrop-blur-md shadow-[0_20px_60px_-15px_rgba(193,91,39,0.12)]">
      <div className="container mx-auto px-4 md:px-6">
        <div className="flex items-center justify-between h-14">
          <Link to="/" className="flex items-center gap-2 font-semibold text-[#9A4A1C] hover:text-[#C15B27] transition-colors">
            <PixelMascot size={32} className="rounded-sm" />
            <span className="text-base hidden sm:inline tracking-tight">Patent Tutor</span>
          </Link>

          <nav className="hidden md:flex items-center gap-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <Button
                  key={item.href}
                  variant={isActive(item.href) ? "ghost" : "ghost"}
                  asChild
                  className={cn(
                    "h-9 px-4 text-sm font-medium transition-all duration-200 rounded-full",
                    isActive(item.href)
                      ? "text-[#C15B27] bg-[#FFE8D0]/70"
                      : "text-[#8B5A3C] hover:text-[#C15B27] hover:bg-[#FFE8D0]/50"
                  )}
                >
                  <Link to={item.href}>
                    <Icon className="h-4 w-4 mr-2" />
                    {item.label}
                  </Link>
                </Button>
              );
            })}
          </nav>

          <div className="hidden md:flex items-center gap-2">
            {auth ? (
              <>
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#FFE8D0]/60 border border-white/70">
                  <User className="h-4 w-4 text-[#9A6A4A]" />
                  <span className="text-sm text-[#5C3A26]">
                    {auth.display_name || auth.login_id}
                  </span>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-9 border-[#D9773E]/40 text-[#C15B27] hover:bg-[#FFE8D0]/60 hover:text-[#9A4A1C] rounded-full"
                  onClick={handleLogout}
                >
                  <LogOut className="h-4 w-4 mr-2" />
                  退出
                </Button>
              </>
            ) : (
              <Button
                variant="outline"
                size="sm"
                className="h-9 border-[#D9773E]/40 text-[#C15B27] hover:bg-[#FFE8D0]/60 hover:text-[#9A4A1C] rounded-full"
                asChild
              >
                <Link to="/auth">
                  <LogIn className="h-4 w-4 mr-2" />
                  登录
                </Link>
              </Button>
            )}
          </div>

          <Button
            variant="ghost"
            size="icon"
            className="md:hidden h-9 w-9 text-[#8B5A3C] hover:text-[#C15B27] hover:bg-[#FFE8D0]/50"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
        </div>

        {mobileMenuOpen && (
          <nav className="md:hidden py-4 border-t border-white/70">
            <div className="flex flex-col gap-1">
              {navItems.map((item) => {
                const Icon = item.icon;
                return (
                  <Button
                    key={item.href}
                    variant={isActive(item.href) ? "ghost" : "ghost"}
                    asChild
                    className={cn(
                      "h-10 px-4 text-left text-sm font-medium transition-all duration-200 justify-start rounded-lg",
                      isActive(item.href)
                        ? "text-[#C15B27] bg-[#FFE8D0]/70"
                        : "text-[#8B5A3C] hover:text-[#C15B27] hover:bg-[#FFE8D0]/50"
                    )}
                  >
                    <Link to={item.href} onClick={() => setMobileMenuOpen(false)}>
                      <Icon className="h-4 w-4 mr-3" />
                      {item.label}
                    </Link>
                  </Button>
                );
              })}
              <div className="border-t border-white/70 my-2 pt-3">
                {auth ? (
                  <div className="flex items-center justify-between px-4 mb-2">
                    <span className="text-sm text-[#5C3A26] flex items-center gap-2">
                      <User className="h-4 w-4 text-[#9A6A4A]" />
                      {auth.display_name || auth.login_id}
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 text-[#C15B27] hover:bg-[#FFE8D0]/60"
                      onClick={() => {
                        handleLogout();
                        setMobileMenuOpen(false);
                      }}
                    >
                      <LogOut className="h-4 w-4" />
                    </Button>
                  </div>
                ) : (
                  <Button
                    variant="outline"
                    className="w-full h-10 border-[#D9773E]/40 text-[#C15B27] hover:bg-[#FFE8D0]/60 rounded-full"
                    asChild
                  >
                    <Link to="/auth" onClick={() => setMobileMenuOpen(false)}>
                      <LogIn className="h-4 w-4 mr-2" />
                      登录 / 注册
                    </Link>
                  </Button>
                )}
              </div>
            </div>
          </nav>
        )}
      </div>
    </header>
  );
}
