"use client";

import React, { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";

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
  const [mounted, setMounted] = useState(false);
  const [coords, setCoords] = useState<{ top: number; left: number; width: number }>({
    top: 0,
    left: 0,
    width: 0,
  });

  const buttonRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const selectedOption = options.find((opt) => opt.value === value);

  useEffect(() => {
    setMounted(true);
  }, []);

  const updatePosition = () => {
    if (buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      setCoords({
        top: rect.bottom + window.scrollY + 4,
        left: rect.left + window.scrollX,
        width: rect.width,
      });
    }
  };

  useEffect(() => {
    if (isOpen) {
      updatePosition();
      window.addEventListener("resize", updatePosition);
      window.addEventListener("scroll", updatePosition, true);
    }
    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [isOpen]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      const isClickInsideButton = buttonRef.current && buttonRef.current.contains(event.target as Node);
      const isClickInsideDropdown = dropdownRef.current && dropdownRef.current.contains(event.target as Node);

      if (!isClickInsideButton && !isClickInsideDropdown) {
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

  useEffect(() => {
    if (isOpen && searchInputRef.current) {
      // Pequeno timeout para garantir renderização do portal no DOM
      const timer = setTimeout(() => searchInputRef.current?.focus(), 50);
      return () => clearTimeout(timer);
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

  const dropdownMenu = isOpen ? (
    <div
      ref={dropdownRef}
      style={{
        position: "absolute",
        top: `${coords.top}px`,
        left: `${coords.left}px`,
        width: `${coords.width}px`,
      }}
      className="z-[9999] rounded-xl border border-slate-200 bg-white shadow-2xl overflow-hidden p-2 space-y-1"
    >
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
      <div className="max-h-48 overflow-y-auto divide-y divide-slate-50 py-1">
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
  ) : null;

  return (
    <div className={`relative w-full ${className}`}>
      {/* Botão Gatilho / Trigger */}
      <button
        ref={buttonRef}
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

      {/* Render via Portal no document.body */}
      {mounted && dropdownMenu && createPortal(dropdownMenu, document.body)}
    </div>
  );
}
