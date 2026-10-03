"use client";

import * as RadixTabs from "@radix-ui/react-tabs";
import type { ReactNode } from "react";

export const Tabs = RadixTabs.Root;

export function TabsList({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
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
  className = "",
}: {
  value: string;
  disabled?: boolean;
  children: ReactNode;
  className?: string;
}) {
  return (
    <RadixTabs.Trigger
      value={value}
      disabled={disabled}
      className={`inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-xs sm:text-sm font-semibold text-slate-600 transition-all hover:bg-slate-200/70 hover:text-slate-900 data-[state=active]:bg-blue-600 data-[state=active]:text-white data-[state=active]:shadow-md disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer ${className}`}
    >
      {children}
    </RadixTabs.Trigger>
  );
}

export function TabsContent({ value, children }: { value: string; children: ReactNode }) {
  return (
    <RadixTabs.Content value={value} className="pt-6">
      {children}
    </RadixTabs.Content>
  );
}
