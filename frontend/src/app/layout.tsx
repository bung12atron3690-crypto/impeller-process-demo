import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "开式叶轮智能工艺 Demo",
  description: "叶轮模型解析、工艺路线与参数包生成",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
