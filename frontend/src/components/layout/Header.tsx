import { Link, useLocation, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { GraduationCap, Home, MessageSquare, FileText, Users, Menu, X, LogIn, LogOut, User } from "lucide-react";
import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { getAuth, clearAuth } from "@/api/auth";
import type { AuthResponse } from "@/api/auth";

const navItems = [
  { href: "/", label: "首页", icon: Home },
  { href: "/onboarding", label: "自评诊断", icon: GraduationCap },
  { href: "/sessions", label: "会话管理", icon: FileText },
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
    <header className="sticky top-0 z-50 border-b border-border/40 bg-background/80 backdrop-blur-md">
      <div className="container mx-auto px-4 md:px-6">
        <div className="flex items-center justify-between h-14">
          <Link to="/" className="flex items-center gap-2 font-semibold text-foreground">
            <GraduationCap className="h-5 w-5 text-primary" />
            <span className="text-base hidden sm:inline">Patent Tutor</span>
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
                    "h-9 px-4 text-sm font-medium transition-all duration-200",
                    isActive(item.href) 
                      ? "text-primary bg-primary/10" 
                      : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
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
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-secondary/50">
                  <User className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">
                    {auth.display_name || auth.login_id}
                  </span>
                </div>
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="h-9"
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
                className="h-9"
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
            className="md:hidden h-9 w-9"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
        </div>

        {mobileMenuOpen && (
          <nav className="md:hidden py-4 border-t border-border/30">
            <div className="flex flex-col gap-1">
              {navItems.map((item) => {
                const Icon = item.icon;
                return (
                  <Button
                    key={item.href}
                    variant={isActive(item.href) ? "ghost" : "ghost"}
                    asChild
                    className={cn(
                      "h-10 px-4 text-left text-sm font-medium transition-all duration-200 justify-start",
                      isActive(item.href) 
                        ? "text-primary bg-primary/10" 
                        : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
                    )}
                  >
                    <Link to={item.href} onClick={() => setMobileMenuOpen(false)}>
                      <Icon className="h-4 w-4 mr-3" />
                      {item.label}
                    </Link>
                  </Button>
                );
              })}
              <div className="border-t border-border/30 my-2 pt-3">
                {auth ? (
                  <div className="flex items-center justify-between px-4 mb-2">
                    <span className="text-sm text-muted-foreground flex items-center gap-2">
                      <User className="h-4 w-4" />
                      {auth.display_name || auth.login_id}
                    </span>
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className="h-8"
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
                    className="w-full h-10"
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
