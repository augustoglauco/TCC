"use client";

import React from "react";
import type { CollectionPurpose } from "@/lib/types/rag";

interface CollectionsPurposeFilterProps {
  filtroPurpose: "todas" | CollectionPurpose;
  totalCount: number;
  chatCount: number;
  b2bCount: number;
  adminCount: number;
  onChange: (v: "todas" | CollectionPurpose) => void;
}

export function CollectionsPurposeFilter({
  filtroPurpose,
  totalCount,
  chatCount,
  b2bCount,
  adminCount,
  onChange,
}: CollectionsPurposeFilterProps) {
  return (
    <div className="mb-4 flex flex-wrap items-center gap-2">
      <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider mr-1">
        Finalidade:
      </span>
      <button
        type="button"
        onClick={() => onChange("todas")}
        className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition-all ${
          filtroPurpose === "todas"
            ? "bg-slate-900 text-white shadow-2xs"
            : "bg-slate-100 text-slate-600 hover:bg-slate-200/80"
        }`}
      >
        Todas ({totalCount})
      </button>
      <button
        type="button"
        onClick={() => onChange("chat")}
        className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition-all ${
          filtroPurpose === "chat"
            ? "bg-blue-600 text-white shadow-2xs"
            : "bg-blue-50 text-blue-700 hover:bg-blue-100/80"
        }`}
      >
        💬 Chat ({chatCount})
      </button>
      <button
        type="button"
        onClick={() => onChange("mcp_b2b")}
        className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition-all ${
          filtroPurpose === "mcp_b2b"
            ? "bg-purple-600 text-white shadow-2xs"
            : "bg-purple-50 text-purple-700 hover:bg-purple-100/80"
        }`}
      >
        🏢 MCP B2B ({b2bCount})
      </button>
      <button
        type="button"
        onClick={() => onChange("admin")}
        className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition-all ${
          filtroPurpose === "admin"
            ? "bg-rose-600 text-white shadow-2xs"
            : "bg-rose-50 text-rose-700 hover:bg-rose-100/80"
        }`}
      >
        🛡️ Admin ({adminCount})
      </button>
    </div>
  );
}
