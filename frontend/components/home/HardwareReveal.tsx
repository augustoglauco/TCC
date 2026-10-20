"use client";

import { useState } from "react";
import Link from "next/link";
import { useChatStore } from "@/lib/hooks/useChatStore";

interface HardwareItem {
  id: string;
  number: string;
  name: string;
  category: string;
  headline: string;
  description: string;
  specs: string[];
  imageSrc: string;
  altImageSrc: string;
}

const HARDWARE_ITEMS: HardwareItem[] = [
  {
    id: "idface",
    number: "01",
    name: "Terminal de Reconhecimento Facial iDFace",
    category: "Controle de Acesso Facial",
    headline: "Identificação Ultrarrápida Sem Contato",
    description:
      "Algoritmo de ponta com inteligência artificial, capacidade para milhares de faces e leitura em menos de 0.2 segundos com autenticação antifraude contra impressões e telas.",
    specs: [
      "Validação em 0.2s",
      "Display Touchscreen",
      "Proteção Antifraude",
      "Comunicação TCP/IP",
    ],
    imageSrc: "/images/produtos/idface-perspectiva.jpg",
    altImageSrc: "/images/produtos/idface-frontal.jpg",
  },
  {
    id: "idblock",
    number: "02",
    name: "Catraca de Pedestal em Inox iDBlock",
    category: "Bloqueios Físicos & Portaria",
    headline: "Engenharia de Alta Durabilidade em Inox",
    description:
      "Desenvolvida em aço inoxidável 304 com acabamento escovado, mecanismo de giro suave e silencioso, e integração completa com leitores faciais, biometria e QR Code.",
    specs: ["Aço Inox 304", "Amortecimento Suave", "Braços Anti-Pânico", "Giro Bidirecional"],
    imageSrc: "/images/produtos/idblock-inox.jpg",
    altImageSrc: "/images/produtos/idblock-facial-inox.jpg",
  },
  {
    id: "rep-idclass",
    number: "03",
    name: "Relógio de Ponto Eletrônico REP iDClass",
    category: "Ponto Eletrônico & RH",
    headline: "Conformidade Total Portaria 671 do MTE",
    description:
      "Registrador eletrônico de ponto homologado pelo Ministério do Trabalho e Emprego, com guilhotina automática, impressão rápida e gestão de jornada conectada em nuvem.",
    specs: ["Homologado Portaria 671", "Bobina até 400m", "Display Colorido", "Nuvem RHiD"],
    imageSrc: "/images/produtos/rep-idclass.jpg",
    altImageSrc: "/images/produtos/idclass-373.jpg",
  },
  {
    id: "idaccess-pro",
    number: "04",
    name: "Controlador de Acesso Biométrico iDAccess Pro",
    category: "Biometria & RFID",
    headline: "Controle de Portas e Eclusas de Alta Densidade",
    description:
      "Equipamento compacto com leitor biométrico de alta resolução e proximidade RFID, relé embarcado para acionamento de fechaduras eletroímã e controle de sensores de porta.",
    specs: [
      "Sensor Biométrico Óptico",
      "Leitor RFID 125kHz/Mifare",
      "Relé Integrado",
      "Web Server Embarcado",
    ],
    imageSrc: "/images/produtos/idaccess-pro.jpg",
    altImageSrc: "/images/produtos/idaccess.jpg",
  },
  {
    id: "idflex",
    number: "05",
    name: "Terminal de Acesso Resistente iDFlex IP65",
    category: "Áreas Externas & Industriais",
    headline: "Proteção Contra Intempéries, Poeira e Água",
    description:
      "Gabinete com certificação IP65 desenvolvido especificamente para instalação em ambientes fabris, estacionamentos e áreas abertas sujeitas a chuva e poeira.",
    specs: ["Proteção IP65", "Ambientes Severos", "Biometria + Cartão", "Alta Resistência"],
    imageSrc: "/images/produtos/idflex-ip65.jpg",
    altImageSrc: "/images/produtos/idpower.jpg",
  },
];

function CabecalhoSecao() {
  return (
    <div
      data-m3-reveal="up"
      className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start border-b border-[#e3e3e8] pb-8"
    >
      <div className="lg:col-span-4">
        <span className="inline-flex items-center gap-2 rounded-full border border-[#191919]/25 bg-white px-4 py-1.5 text-xs font-bold uppercase tracking-[0.2em] text-[#191919]">
          <span className="h-2 w-2 rounded-full bg-[#16c0dd]" />
          Destaques de Engenharia
        </span>
      </div>

      <div className="lg:col-span-8 space-y-3">
        <h2 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-[#191919] leading-[1.1]">
          Hardware de Ponta para <span className="text-[#16c0dd]">Controle de Acesso</span>
        </h2>
        <p className="text-sm sm:text-base text-[#4d4d52] max-w-2xl">
          Passe o cursor ou toque nas linhas numeradas ao lado para inspecionar a fotografia oficial
          do equipamento e consultar suas especificações técnicas.
        </p>
      </div>
    </div>
  );
}

function VitrineProduto({ activeItem }: { activeItem: HardwareItem }) {
  return (
    <div className="antra-blurIn lg:col-span-6 m3-photo-card relative min-h-[480px] sm:min-h-[550px] rounded-[24px] border border-[#e3e3e8] bg-gradient-to-b from-white via-slate-50 to-slate-200 p-6 sm:p-8 flex flex-col justify-between shadow-[0_20px_55px_rgba(15,23,42,0.1)]">
      {/* Topo da vitrine com badge de categoria e miniatura de segundo ângulo */}
      <div className="relative z-10 flex items-start justify-between gap-4">
        <span className="inline-flex items-center gap-2 rounded-full bg-slate-950/90 px-4 py-1.5 text-xs font-bold text-[#16c0dd] shadow-md">
          <span className="h-2 w-2 rounded-full bg-[#16c0dd] animate-pulse" />
          {activeItem.category}
        </span>

        <div className="flex items-center gap-2.5 rounded-2xl border border-slate-200 bg-white/95 p-2 shadow-lg">
          <div className="h-12 w-12 overflow-hidden rounded-xl bg-slate-50 p-1">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={activeItem.altImageSrc}
              alt={`${activeItem.name} vista alternativa`}
              className="h-full w-full object-contain"
            />
          </div>
          <div className="pr-2 hidden sm:block">
            <span className="block text-[10px] font-mono uppercase text-slate-400">
              Série Oficial
            </span>
            <span className="text-xs font-extrabold text-slate-900">{activeItem.number} / 05</span>
          </div>
        </div>
      </div>

      {/* Imagem Central de Alta Resolução do Produto */}
      <div className="relative z-0 my-auto py-4 flex items-center justify-center h-64 sm:h-72">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={activeItem.imageSrc}
          alt={activeItem.name}
          className="max-h-full max-w-full object-contain drop-shadow-[0_22px_32px_rgba(15,23,42,0.22)] transition-transform duration-500 hover:scale-105"
        />
      </div>

      {/* Caixa Frosted Glass Flutuante na Base (.img-content de m3glass.com: rgba(21,24,31,.78) + blur(29px)) */}
      <div className="relative z-10 rounded-[24px] border border-white/15 bg-[#15181f]/88 p-5 sm:p-6 text-white backdrop-blur-[29px] shadow-2xl space-y-3.5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-lg sm:text-xl font-extrabold text-white tracking-tight">
              {activeItem.name}
            </h3>
            <p className="text-xs sm:text-sm font-bold text-[#16c0dd] mt-0.5">
              {activeItem.headline}
            </p>
          </div>
          <span className="font-mono text-xs font-bold text-white/60 shrink-0">
            #{activeItem.number}
          </span>
        </div>

        <p className="text-xs text-slate-200 leading-relaxed">{activeItem.description}</p>

        <div className="grid grid-cols-2 gap-2 pt-1 text-xs">
          {activeItem.specs.map((spec) => (
            <div key={spec} className="flex items-center gap-2 text-slate-200">
              <span className="h-1.5 w-1.5 rounded-full bg-[#16c0dd]" />
              <span>{spec}</span>
            </div>
          ))}
        </div>

        <div className="pt-2 border-t border-white/10 flex flex-wrap items-center justify-between gap-3">
          <Link
            href="/produtos"
            className="inline-flex items-center gap-2 rounded-full bg-[#16c0dd] hover:bg-cyan-300 px-4 py-2 text-xs font-extrabold text-slate-950 transition-all shadow-md"
          >
            <span>Ver no Catálogo</span>
            <span>→</span>
          </Link>

          <button
            type="button"
            onClick={() => useChatStore.getState().open()}
            className="inline-flex items-center gap-1.5 text-xs font-bold text-white/90 hover:text-[#16c0dd] transition-colors cursor-pointer"
          >
            <span>Consultar estoque via IA</span>
            <span>↗</span>
          </button>
        </div>
      </div>
    </div>
  );
}

function ItemLista({
  item,
  isSelected,
  onSelecionar,
}: {
  item: HardwareItem;
  isSelected: boolean;
  onSelecionar: () => void;
}) {
  return (
    <div
      onMouseEnter={onSelecionar}
      onClick={onSelecionar}
      className={`group flex items-center justify-between gap-4 py-6 px-4 sm:px-5 transition-all duration-300 cursor-pointer ${
        isSelected
          ? "bg-white shadow-[0_8px_30px_rgba(0,0,0,0.05)] rounded-2xl border-transparent"
          : "hover:bg-white/60"
      }`}
    >
      <div className="flex items-center gap-4 sm:gap-5 min-w-0">
        <span
          className={`font-mono text-base sm:text-lg font-extrabold w-9 shrink-0 transition-colors ${
            isSelected ? "text-[#16c0dd]" : "text-[#9f9fa4] group-hover:text-[#191919]"
          }`}
        >
          {item.number}
        </span>

        <div className="h-12 w-12 shrink-0 overflow-hidden rounded-xl border border-slate-200 bg-white p-1 shadow-xs">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={item.imageSrc}
            alt=""
            aria-hidden="true"
            className="h-full w-full object-contain"
          />
        </div>

        <div className="min-w-0">
          <h4
            className={`text-base sm:text-xl font-extrabold truncate transition-colors ${
              isSelected ? "text-[#191919]" : "text-[#4d4d52] group-hover:text-[#191919]"
            }`}
          >
            {item.name}
          </h4>
          <p className="text-xs text-[#9f9fa4] truncate mt-0.5">{item.category}</p>
        </div>
      </div>

      {/* Botão Circular .arrow idêntico ao .feature-item .arrow do M3 Glass */}
      <div
        className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-base font-bold transition-all duration-300 ${
          isSelected
            ? "bg-[#16c0dd] text-white shadow-md shadow-[#16c0dd]/30 -rotate-45 scale-105"
            : "bg-slate-200/80 text-[#191919] group-hover:bg-[#16c0dd] group-hover:text-white group-hover:-rotate-45"
        }`}
      >
        →
      </div>
    </div>
  );
}

export default function HardwareReveal() {
  const [activeIndex, setActiveIndex] = useState(0);
  const activeItem = HARDWARE_ITEMS[activeIndex];

  return (
    <section className="space-y-10 py-8 sm:py-12">
      <CabecalhoSecao />

      {/* Grid Principal M3 Glass (.feature-img à esquerda + .feature-item-list 01–05 à direita) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
        <VitrineProduto key={activeItem.id} activeItem={activeItem} />

        {/* Coluna Direita: Lista Numerada Interativa 01–05 (.feature-item-list de m3glass.com) */}
        <div className="lg:col-span-6 divide-y divide-[#e3e3e8] border-t border-b border-[#e3e3e8]">
          {HARDWARE_ITEMS.map((item, idx) => (
            <ItemLista
              key={item.id}
              item={item}
              isSelected={idx === activeIndex}
              onSelecionar={() => setActiveIndex(idx)}
            />
          ))}
        </div>
      </div>
    </section>
  );
}
