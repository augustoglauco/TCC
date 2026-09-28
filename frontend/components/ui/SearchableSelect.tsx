"use client";

import React, { useState, useRef, useEffect } from "react";

export interface SearchableSelectOption {
  value: string;
  label: string;
  sublabel?: string;
}

interface SearchableSelectProps {
  options: SearchableSelectOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}

export default function SearchableSelect({
  options,
  value,
  onChange,
  placeholder = "-- Selecione uma opção --",
  disabled = false,
  className = "",
}: SearchableSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const selectedOption = options.find((opt) => opt.value === value);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  useEffect(() => {
    if (isOpen && searchInputRef.current) {
      searchInputRef.current.focus();
    }
  }, [isOpen]);

  const filteredOptions = options.filter((opt) => {
    const term = searchTerm.toLowerCase().trim();
    if (!term) return true;
    return (
      opt.label.toLowerCase().includes(term) ||
      (opt.sublabel && opt.sublabel.toLowerCase().includes(term)) ||
      opt.value.toLowerCase().includes(term)
    );
  });

  const handleSelect = (val: string) => {
    onChange(val);
    setIsOpen(false);
    setSearchTerm("");
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    onChange("");
    setSearchTerm("");
  };

  return (
    <div ref={containerRef} className={`relative w-full ${className}`}>
      {/* Botão Gatilho / Trigger */}
      <button
        type="button"
        disabled={disabled}
        onClick={() => setIsOpen((prev) => !prev)}
        className="w-full flex items-center justify-between gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-900 shadow-2xs hover:border-blue-400 focus:border-blue-500 focus:outline-none disabled:opacity-50 cursor-pointer"
      >
        <span className="truncate text-left">
          {selectedOption ? (
            <span>
              <span className="font-semibold text-slate-900">{selectedOption.label}</span>
              {selectedOption.sublabel && (
                <span className="ml-1.5 text-slate-500 text-[11px]">({selectedOption.sublabel})</span>
              )}
            </span>
          ) : (
            <span className="text-slate-400">{placeholder}</span>
          )}
        </span>
        <div className="flex items-center gap-1 shrink-0">
          {value && (
            <span
              onClick={handleClear}
              className="text-slate-400 hover:text-slate-600 p-0.5 rounded text-xs leading-none"
              title="Limpar seleção"
            >
              ✕
            </span>
          )}
          <span className="text-slate-400 text-[10px]">{isOpen ? "▲" : "▼"}</span>
        </div>
      </button>

      {/* Dropdown Flutuante */}
      {isOpen && (
        <div className="absolute left-0 right-0 top-full mt-1 z-50 rounded-xl border border-slate-200 bg-white shadow-xl overflow-hidden p-2 space-y-1 animate-in fade-in slide-in-from-top-1 duration-150">
          {/* Input de Busca Interna */}
          <div className="relative">
            <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 text-xs">🔍</span>
            <input
              ref={searchInputRef}
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Digite para filtrar produtos..."
              className="w-full rounded-md border border-slate-200 bg-slate-50 pl-8 pr-3 py-1.5 text-xs text-slate-900 focus:border-blue-500 focus:bg-white focus:outline-none"
            />
            {searchTerm && (
              <button
                type="button"
                onClick={() => setSearchTerm("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 text-xs"
              >
                ✕
              </button>
            )}
          </div>

          {/* Lista de Opções Filtradas */}
          <div className="max-h-56 overflow-y-auto divide-y divide-slate-50 py-1">
            {filteredOptions.length === 0 ? (
              <div className="p-3 text-center text-xs text-slate-400 italic">
                Nenhum produto encontrado com "{searchTerm}"
              </div>
            ) : (
              filteredOptions.map((opt) => {
                const isSelected = opt.value === value;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => handleSelect(opt.value)}
                    className={`w-full flex items-center justify-between px-2.5 py-2 text-xs text-left rounded-md transition-colors cursor-pointer ${
                      isSelected
                        ? "bg-blue-50 text-blue-900 font-semibold"
                        : "hover:bg-slate-100 text-slate-800"
                    }`}
                  >
                    <span className="truncate">
                      <span>{opt.label}</span>
                      {opt.sublabel && (
                        <span className="ml-2 text-slate-500 text-[11px] font-normal">
                          {opt.sublabel}
                        </span>
                      )}
                    </span>
                    {isSelected && <span className="text-blue-600 font-bold ml-2">✓</span>}
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
