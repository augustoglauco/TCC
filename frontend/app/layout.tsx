import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import ChatWidget from "@/components/chat/ChatWidget";
import Footer from "@/components/layout/Footer";
import Header from "@/components/layout/Header";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Empresa Fictícia TCC",
  description: "Assistente virtual multimodal — protótipo de TCC.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col bg-zinc-50 text-gray-900">
        <Header />
        <main className="flex-1">{children}</main>
        <Footer />
        {/* Widget de chat global — presente em todas as rotas (docs/FRONTEND.md §2) */}
        <ChatWidget />
      </body>
    </html>
  );
}
