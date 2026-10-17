"use client";

import { useState } from "react";
import Link from "next/link";

interface HardwareItem {
  id: string;
  number: string;
  name: string;
  category: string;
  headline: string;
  description: string;
  specs: string[];
  imageSrc?: string;
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
    imageSrc: "/images/showcase/idface-frontal.jpg",
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
    imageSrc: "/images/showcase/idblock-inox.jpg",
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
    imageSrc: "/images/showcase/rep-idclass.jpg",
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
    imageSrc: "/images/showcase/idaccess-pro.jpg",
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
    imageSrc: "/images/showcase/idflex-ip65.jpg",
  },
];

export default function HardwareReveal() {
  const [activeIndex, setActiveIndex] = useState(0);
  const activeItem = HARDWARE_ITEMS[activeIndex];

  return (
    <section className="space-y-8 py-6 sm:py-10">
      {/* Cabeçalho da Seção estilo M3 Glass */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <span className="text-xs font-bold uppercase tracking-widest text-blue-600">
            Destaques de Engenharia
          </span>
          <h2 className="text-2xl sm:text-4xl font-extrabold tracking-tight text-slate-900 mt-1">
            Hardware de Ponta para{" "}
            <span className="bg-gradient-to-r from-blue-600 via-indigo-600 to-sky-600 bg-clip-text text-transparent">
              Controle de Acesso
            </span>
          </h2>
        </div>
        <p className="text-xs sm:text-sm text-slate-500 max-w-md">
          Explore as tecnologias oficiais da Control iD integradas ao nosso assistente inteligente e
          protocolo MCP.
        </p>
      </div>

      {/* Grid Principal M3 Glass (Display Visual 50% + Lista 01-05 50%) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-stretch">
        {/* Painel Esquerdo: Display Visual de Hardware */}
        <div className="lg:col-span-6 rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-950 to-slate-900 p-6 sm:p-8 text-white flex flex-col justify-between shadow-xl min-h-[420px]">
          <div>
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-500/20 px-3 py-1 text-xs font-bold text-blue-300">
                {activeItem.category}
              </span>
              <span className="font-mono text-sm text-slate-400">{activeItem.number} / 05</span>
            </div>

            <div className="mt-6 space-y-2">
              <h3 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
                {activeItem.name}
              </h3>
              <p className="text-sm font-semibold text-blue-400">{activeItem.headline}</p>
              <p className="text-xs sm:text-sm text-slate-300 leading-relaxed pt-2">
                {activeItem.description}
              </p>
            </div>
          </div>

          <div className="pt-6 border-t border-slate-800 space-y-4">
            <div className="grid grid-cols-2 gap-2 text-xs">
              {activeItem.specs.map((spec) => (
                <div key={spec} className="flex items-center gap-2 text-slate-300">
                  <span className="h-1.5 w-1.5 rounded-full bg-blue-400" />
                  <span>{spec}</span>
                </div>
              ))}
            </div>

            <div className="pt-2 flex items-center justify-between">
              <Link
                href="/produtos"
                className="inline-flex items-center gap-2 text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 px-4 py-2.5 rounded-xl shadow-md transition-all"
              >
                <span>Ver no Catálogo</span>
                <span>›</span>
              </Link>
              <span className="text-[11px] text-slate-400">Homologação Oficial Control iD</span>
            </div>
          </div>
        </div>

        {/* Painel Direito: Lista Numerada 01 a 05 com seleção por hover e toque */}
        <div className="lg:col-span-6 flex flex-col justify-center space-y-3">
          {HARDWARE_ITEMS.map((item, idx) => {
            const isSelected = idx === activeIndex;
            return (
              <div
                key={item.id}
                onMouseEnter={() => setActiveIndex(idx)}
                onClick={() => setActiveIndex(idx)}
                className={`group flex items-center justify-between p-4 sm:p-5 rounded-2xl border transition-all cursor-pointer ${
                  isSelected
                    ? "border-blue-500 bg-blue-50/70 shadow-md translate-x-1"
                    : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/80"
                }`}
              >
                <div className="flex items-center gap-4 min-w-0">
                  <span
                    className={`text-sm sm:text-base font-mono font-bold px-2.5 py-1 rounded-lg ${
                      isSelected ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {item.number}
                  </span>
                  <div className="min-w-0">
                    <h4
                      className={`text-sm sm:text-base font-bold truncate ${
                        isSelected ? "text-blue-900" : "text-slate-800 group-hover:text-slate-900"
                      }`}
                    >
                      {item.name}
                    </h4>
                    <p className="text-xs text-slate-500 truncate">{item.category}</p>
                  </div>
                </div>

                <div
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-transform ${
                    isSelected
                      ? "bg-blue-600 text-white translate-x-1"
                      : "bg-slate-100 text-slate-400 group-hover:bg-slate-200 group-hover:text-slate-600"
                  }`}
                >
                  ›
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
