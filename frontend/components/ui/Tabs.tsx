"use client";

import * as RadixTabs from "@radix-ui/react-tabs";
import type { ReactNode } from "react";

export const Tabs = RadixTabs.Root;

export function TabsList({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <RadixTabs.List className={`flex flex-wrap gap-1 border-b border-slate-200 ${className}`}>
      {children}
    </RadixTabs.List>
  );
}

export function TabsTrigger({
  value,
  disabled,
  children,
}: {
  value: string;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <RadixTabs.Trigger
      value={value}
      disabled={disabled}
      className="rounded-lg px-3.5 py-2 text-xs sm:text-sm font-semibold text-slate-600 transition-all hover:bg-slate-100 hover:text-slate-900 data-[state=active]:bg-slate-900 data-[state=active]:text-white data-[state=active]:shadow-sm disabled:cursor-not-allowed disabled:opacity-40"
    >
      {children}
    </RadixTabs.Trigger>
  );
}

export function TabsContent({ value, children }: { value: string; children: ReactNode }) {
  return <RadixTabs.Content value={value} className="pt-6">{children}</RadixTabs.Content>;
}
