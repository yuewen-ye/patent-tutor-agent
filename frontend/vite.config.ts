import path from "path";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  const apiBaseUrl = env.VITE_API_BASE_URL || "http://localhost:8000";
  const useProxy = apiBaseUrl === "/api";

  return {
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      port: 5173,
      host: true,
      // 开发时若 VITE_API_BASE_URL=/api，使用代理转发到后端，避免 CORS 配置问题
      proxy: useProxy
        ? {
            "/api": {
              target: "http://localhost:8000",
              changeOrigin: true,
              rewrite: (p) => p.replace(/^\/api/, ""),
            },
          }
        : undefined,
    },
  };
});
