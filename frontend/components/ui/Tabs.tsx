"use client";

import * as RadixTabs from "@radix-ui/react-tabs";
import type { ReactNode } from "react";

export const Tabs = RadixTabs.Root;

export function TabsList({ children }: { children: ReactNode }) {
  return (
    <RadixTabs.List className="flex gap-1 border-b border-gray-200">{children}</RadixTabs.List>
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
      className="px-4 py-2 text-sm font-medium text-gray-600 data-[state=active]:border-b-2 data-[state=active]:border-gray-900 data-[state=active]:text-gray-900 disabled:cursor-not-allowed disabled:opacity-40"
    >
      {children}
    </RadixTabs.Trigger>
  );
}

export function TabsContent({ value, children }: { value: string; children: ReactNode }) {
  return <RadixTabs.Content value={value} className="pt-6">{children}</RadixTabs.Content>;
}
