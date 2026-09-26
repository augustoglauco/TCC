"use client";

import React, { useState, useRef, useEffect } from "react";

interface CategoryFilterProps {
  selectedCategories: string[];
  onChange: (categories: string[]) => void;
  availableCategories: string[];
  categoryCounts?: Record<string, number>;
}

export default function CategoryFilter({
  selectedCategories,
  onChange,
  availableCategories,
  categoryCounts = {},
}: CategoryFilterProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Fecha ao clicar fora
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  // Lista combinada de categorias (disponíveis + selecionadas que talvez não estejam na lista)
  const allKnownCategories = Array.from(
    new Set([...availableCategories, ...selectedCategories])
  ).filter(Boolean);

  const filteredCategories = allKnownCategories.filter((cat) =>
    cat.toLowerCase().includes(searchTerm.toLowerCase().trim())
  );

  const isCustomCandidate =
    searchTerm.trim() &&
    !allKnownCategories.some(
      (c) => c.toLowerCase() === searchTerm.toLowerCase().trim()
    );

  const handleToggleCategory = (cat: string) => {
    if (selectedCategories.includes(cat)) {
      onChange(selectedCategories.filter((c) => c !== cat));
    } else {
      onChange([...selectedCategories, cat]);
    }
  };

  const handleSelectAll = () => {
    onChange([...allKnownCategories]);
  };

  const handleClearAll = () => {
    onChange([]);
  };

  const handleAddCustom = () => {
    if (searchTerm.trim()) {
      const newCat = searchTerm.trim();
      if (!selectedCategories.includes(newCat)) {
        onChange([...selectedCategories, newCat]);
      }
      setSearchTerm("");
    }
  };

  return (
    <div className="relative inline-block text-left" ref={dropdownRef}>
      {/* Botão Gatilho do Dropdown */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className={`flex items-center gap-2 rounded-lg border px-3.5 py-2 text-sm font-medium transition-all shadow-2xs ${
          selectedCategories.length > 0
            ? "border-blue-600 bg-blue-50/70 text-blue-800 ring-1 ring-blue-600/30"
            : "border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
        }`}
        aria-haspopup="true"
        aria-expanded={isOpen}
      >
        <span>🏷️</span>
        <span>
          {selectedCategories.length === 0
            ? "Todas as Categorias"
            : selectedCategories.length === 1
            ? selectedCategories[0]
            : `${selectedCategories.length} categorias selecionadas`}
        </span>
        {selectedCategories.length > 0 && (
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-600 text-[11px] font-bold text-white">
            {selectedCategories.length}
          </span>
        )}
        <svg
          className={`h-4 w-4 text-gray-500 transition-transform ${isOpen ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Painel Dropdown Popover */}
      {isOpen && (
        <div className="absolute left-0 sm:right-0 sm:left-auto z-40 mt-2 w-72 sm:w-80 rounded-xl border border-gray-200 bg-white p-3 shadow-xl ring-1 ring-black/5 animate-in fade-in zoom-in-95 duration-100">
          {/* Campo de Busca Rápida de Categorias */}
          <div className="relative mb-2">
            <span className="absolute inset-y-0 left-0 flex items-center pl-2.5 text-gray-400 text-xs">
              🔍
            </span>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && isCustomCandidate) {
                  e.preventDefault();
                  handleAddCustom();
                }
              }}
              placeholder="Buscar ou adicionar categoria..."
              className="w-full rounded-lg border border-gray-200 bg-gray-50/80 py-1.5 pl-8 pr-3 text-xs text-gray-800 placeholder:text-gray-400 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          {/* Ações rápidas */}
          <div className="flex items-center justify-between border-b border-gray-100 pb-2 mb-2 px-1 text-[11px]">
            <button
              type="button"
              onClick={handleSelectAll}
              className="font-semibold text-blue-600 hover:text-blue-800"
            >
              Marcar todas
            </button>
            <span className="text-gray-300">|</span>
            <button
              type="button"
              onClick={handleClearAll}
              className="font-semibold text-gray-500 hover:text-gray-700"
            >
              Desmarcar todas
            </button>
          </div>

          {/* Opção para adicionar categoria personalizada se digitada */}
          {isCustomCandidate && (
            <div className="mb-2 rounded-lg bg-blue-50/70 p-2 text-xs">
              <span className="text-gray-600">Filtrar por novo termo:</span>
              <button
                type="button"
                onClick={handleAddCustom}
                className="mt-1 flex w-full items-center justify-between rounded-md bg-blue-600 px-2 py-1 font-semibold text-white hover:bg-blue-700"
              >
                <span>+ &quot;{searchTerm.trim()}&quot;</span>
                <span className="text-[10px] opacity-80">(Enter)</span>
              </button>
            </div>
          )}

          {/* Lista Rolável de Categorias com Checkboxes */}
          <div className="max-h-56 overflow-y-auto space-y-1 pr-1">
            {filteredCategories.length === 0 && !isCustomCandidate ? (
              <div className="py-4 text-center text-xs text-gray-400">
                Nenhuma categoria encontrada
              </div>
            ) : (
              filteredCategories.map((cat) => {
                const isChecked = selectedCategories.includes(cat);
                const count = categoryCounts[cat];

                return (
                  <label
                    key={cat}
                    className={`flex items-center justify-between rounded-md px-2.5 py-1.5 text-xs cursor-pointer select-none transition-colors ${
                      isChecked
                        ? "bg-blue-50 font-semibold text-blue-900"
                        : "text-gray-700 hover:bg-gray-100"
                    }`}
                  >
                    <div className="flex items-center gap-2 truncate">
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => handleToggleCategory(cat)}
                        className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                      <span className="truncate">{cat}</span>
                    </div>

                    {count !== undefined && (
                      <span
                        className={`rounded-full px-1.5 py-0.2 text-[10px] font-medium ${
                          isChecked
                            ? "bg-blue-200 text-blue-800"
                            : "bg-gray-100 text-gray-500"
                        }`}
                      >
                        {count}
                      </span>
                    )}
                  </label>
                );
              })
            )}
          </div>

          {/* Rodapé com contagem */}
          <div className="mt-2 border-t border-gray-100 pt-2 text-[11px] text-gray-500 flex items-center justify-between px-1">
            <span>
              {selectedCategories.length === 0
                ? "Sem filtro (mostra tudo)"
                : `${selectedCategories.length} de ${allKnownCategories.length} ativas`}
            </span>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="rounded bg-gray-100 px-2 py-0.5 font-medium text-gray-700 hover:bg-gray-200"
            >
              Fechar
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
