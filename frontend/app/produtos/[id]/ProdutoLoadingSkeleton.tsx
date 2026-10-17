"use client";

export function ProdutoLoadingSkeleton() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:py-14 animate-pulse">
      <div className="h-4 w-36 bg-slate-200 rounded mb-8" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
        <div className="aspect-4/3 w-full bg-slate-200 rounded-2xl" />
        <div className="space-y-4">
          <div className="h-5 w-24 bg-slate-200 rounded" />
          <div className="h-8 w-3/4 bg-slate-200 rounded" />
          <div className="h-6 w-32 bg-slate-200 rounded" />
          <div className="h-20 w-full bg-slate-200 rounded" />
          <div className="h-12 w-full bg-slate-200 rounded" />
        </div>
      </div>
    </div>
  );
}
