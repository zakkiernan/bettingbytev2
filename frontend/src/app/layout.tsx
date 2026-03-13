import type { ReactNode } from "react";
import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";

import { AuthProvider } from "@/components/providers/auth-provider";

import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
});

const jetBrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "BettingByte",
  description: "Dark-first BettingByte frontend scaffold for dashboard, props, live tracking, and picks.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html className="dark" lang="en">
      <body className={`${inter.variable} ${jetBrainsMono.variable} font-sans`}>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
