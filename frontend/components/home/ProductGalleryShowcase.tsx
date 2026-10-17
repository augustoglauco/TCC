"use client";
/* eslint-disable @next/next/no-img-element */

import { useState } from "react";
import Link from "next/link";

interface ProjectItem {
  id: string;
  title: string;
  subtitle: string;
  tag: string;
  spec: string;
  image: string;
  tall: boolean;
}

const PROJECTS: ProjectItem[] = [
  {
    id: "idface-max",
    title: "Terminal Facial iDFace Max",
    subtitle: "Hospitais, Indústrias & Condomínios Corporativos",
    tag: "Facial 3D • IP65",
    spec: "Até 100.000 faces • Live Detection",
    image: "/images/produtos/idface-max.jpg",
    tall: true,
  },
  {
    id: "idblock-next",
    title: "Catraca iDBlock Next Facial",
    subtitle: "Recepções Executivas & Lobbies A+",
    tag: "Inox Escovado",
    spec: "Pedestal Integrado • 2 Leitores Faciais",
    image: "/images/produtos/idblock-next-facial.jpg",
    tall: false,
  },
  {
    id: "idblock-pcd",
    title: "Porta Giratória iDBlock PcD",
    subtitle: "Acessibilidade Universal & Passagem Larga",
    tag: "Acessibilidade PNE",
    spec: "Abertura Motorizada 90° em Inox",
    image: "/images/produtos/idblock-pcd.jpg",
    tall: true,
  },
  {
    id: "rep-idclass",
    title: "Relógio de Ponto REP iDClass",
    subtitle: "Conformidade Trabalhista & Portaria 671 MTE",
    tag: "Homologado INMETRO",
    spec: "Biometria + Proximidade + Impressora Térmica",
    image: "/images/produtos/rep-idclass.jpg",
    tall: false,
  },
];

interface GalleryPhoto {
  src: string;
  title: string;
  category: string;
}

const GALLERY_ROW_1: GalleryPhoto[] = [
  {
    src: "/images/produtos/idface-frontal.jpg",
    title: "iDFace Frontal",
    category: "Reconhecimento Facial",
  },
  {
    src: "/images/produtos/idblock-facial-inox.jpg",
    title: "iDBlock Facial Inox",
    category: "Catracas",
  },
  {
    src: "/images/produtos/idaccess-pro.jpg",
    title: "iDAccess Pro",
    category: "Controladores",
  },
  {
    src: "/images/produtos/idclass-373.jpg",
    title: "iDClass 373",
    category: "Ponto Eletrônico",
  },
  {
    src: "/images/produtos/idbio.jpg",
    title: "Leitor Biométrico iDBio",
    category: "Biometria USB",
  },
  {
    src: "/images/produtos/idblock-preto.jpg",
    title: "iDBlock Preta Carbon",
    category: "Catracas",
  },
];

const GALLERY_ROW_2: GalleryPhoto[] = [
  {
    src: "/images/produtos/idflex-ip65.jpg",
    title: "iDFlex IP65",
    category: "Controle de Acesso",
  },
  {
    src: "/images/produtos/idblock-facial-preta.jpg",
    title: "iDBlock Facial Preta",
    category: "Catracas",
  },
  {
    src: "/images/produtos/idbox.jpg",
    title: "Controladora iDBox",
    category: "Automação 4 Portas",
  },
  {
    src: "/images/produtos/printid-touch.jpg",
    title: "Print iD Touch",
    category: "Impressão Térmica",
  },
  {
    src: "/images/produtos/idpower.jpg",
    title: "Fonte Nobreak iDPower",
    category: "Infraestrutura",
  },
  {
    src: "/images/produtos/idface-perspectiva.jpg",
    title: "iDFace Perspectiva",
    category: "Reconhecimento Facial",
  },
];

export default function ProductGalleryShowcase() {
  const [selectedPhoto, setSelectedPhoto] = useState<GalleryPhoto | null>(null);

  return (
    <div className="space-y-20">
      {/* SECTION 1: M3 Glass .project-section (Staggered Tall Rounded-24px Portfolio Cards) */}
      <section className="project-section relative overflow-hidden pt-6 pb-4">
        <span
          aria-hidden="true"
          className="m3-watermark-light right-2 -top-4 text-[75px] sm:text-[140px] lg:text-[190px]"
        >
          Portfolio
        </span>

        <div className="relative z-10 flex flex-col md:flex-row md:items-end justify-between gap-6 mb-12">
          <div data-m3-reveal="left">
            <div className="inline-flex items-center gap-2.5 text-xs font-extrabold uppercase tracking-[0.22em] text-[#191919] mb-3">
              <span className="h-2.5 w-2.5 rounded-full bg-[#16c0dd] shadow-[0_0_10px_#16c0dd]" />
              Vitrine de Equipamentos Fictícia
            </div>
            <h2 className="text-3xl sm:text-4xl lg:text-[44px] font-extrabold tracking-tight text-[#191919] leading-[1.12]">
              Engenharia Visual &amp;{" "}
              <span className="text-[#16c0dd]">Hardware de Alta Precisão</span>
            </h2>
          </div>

          <div data-m3-reveal="right">
            <Link href="/produtos" className="tl-primary-btn">
              <span>Explorar Catálogo Completo</span>
              <span className="icon" aria-hidden="true">
                ↗
              </span>
            </Link>
          </div>
        </div>

        {/* Staggered Portfolio Columns (.project-item.item-1 vs .item-2) */}
        <div className="relative z-10 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 items-start">
          {PROJECTS.map((project, idx) => (
            <div
              key={project.id}
              data-m3-reveal="bottom"
              data-m3-delay={idx * 100}
              className={`project-item group relative overflow-hidden rounded-[24px] border-[8px] border-white bg-white shadow-xl transition-all duration-500 hover:shadow-2xl hover:-translate-y-2 ${
                project.tall ? "h-[430px] sm:h-[470px]" : "h-[380px] sm:h-[420px] lg:mt-10"
              }`}
            >
              <img
                src={project.image}
                alt={project.title}
                className="h-full w-full object-cover object-center group-hover:scale-110 transition-transform duration-700"
              />

              {/* Subtle dark gradient overlay */}
              <div
                aria-hidden="true"
                className="absolute inset-0 bg-gradient-to-t from-[#100d0b]/95 via-[#100d0b]/35 to-transparent"
              />

              {/* Floating Top-Left Pill Tag (M3 Glass .project-thumb span style) */}
              <span className="absolute top-5 left-5 inline-flex items-center gap-1.5 rounded-full border border-white/80 bg-[#191919]/65 backdrop-blur-md px-3.5 py-1.5 text-[11px] font-extrabold uppercase tracking-wider text-white group-hover:bg-[#16c0dd] group-hover:border-[#16c0dd] group-hover:text-[#191919] transition-colors">
                {project.tag}
              </span>

              {/* Bottom Content */}
              <div className="absolute inset-x-0 bottom-0 p-6 text-white">
                <span className="text-[11px] font-bold uppercase tracking-widest text-[#16c0dd]">
                  {project.spec}
                </span>
                <h3 className="text-xl font-extrabold tracking-tight text-white mt-1 leading-snug">
                  <Link
                    href="/produtos"
                    className="hover:text-[#16c0dd] transition-colors focus:outline-none"
                  >
                    {project.title}
                  </Link>
                </h3>
                <p className="text-xs text-white/75 mt-1.5 line-clamp-2">{project.subtitle}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* SECTION 2: M3 Glass .gallary-section (Dual Opposite-Direction Scroll-Scrubbed Photo Ribbons) */}
      <section className="gallary-section relative overflow-hidden rounded-[24px] bg-[#14161b] border border-white/10 py-14 sm:py-18 text-white shadow-2xl">
        <span
          aria-hidden="true"
          className="m3-watermark-dark left-6 top-2 text-[75px] sm:text-[140px] lg:text-[185px]"
        >
          Gallery
        </span>

        <div className="relative z-10 px-6 sm:px-10 lg:px-14 mb-10 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div data-m3-reveal="left">
            <div className="inline-flex items-center gap-2.5 text-xs font-extrabold uppercase tracking-[0.22em] text-[#16c0dd] mb-2">
              <span className="h-2.5 w-2.5 rounded-full bg-[#16c0dd] shadow-[0_0_10px_#16c0dd]" />
              Galeria Fotográfica Real • 18 Equipamentos
            </div>
            <h2 className="text-2xl sm:text-4xl font-extrabold tracking-tight text-white">
              Linha Completa <span className="text-[#16c0dd]">Fictícia em Detalhes</span>
            </h2>
          </div>
          <p className="text-xs sm:text-sm text-white/65 max-w-sm">
            Role a página para explorar os painéis fotográficos dinâmicos ou clique em qualquer
            equipamento para ampliar em alta definição.
          </p>
        </div>

        {/* Ribbon 1: Scrolls Left on Page Scroll */}
        <div className="relative z-10 overflow-hidden py-3">
          <div
            data-m3-scroll-x="-0.14"
            className="flex items-center gap-5 px-6 will-change-transform transition-transform duration-150 ease-out"
          >
            {[...GALLERY_ROW_1, ...GALLERY_ROW_1].map((photo, idx) => (
              <button
                key={`row1-${photo.src}-${idx}`}
                type="button"
                onClick={() => setSelectedPhoto(photo)}
                className="gallary-item m3-photo-card group relative shrink-0 w-[250px] sm:w-[300px] h-[200px] sm:h-[225px] rounded-[18px] border-4 border-white/15 bg-white overflow-hidden shadow-lg cursor-pointer text-left focus:outline-none focus:ring-2 focus:ring-[#16c0dd]"
              >
                <img
                  src={photo.src}
                  alt={photo.title}
                  className="h-full w-full object-cover group-hover:scale-110 transition-transform duration-500"
                />
                <div className="absolute inset-0 bg-[#191919]/60 opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex flex-col justify-end p-4">
                  <span className="text-[10px] font-extrabold uppercase tracking-widest text-[#16c0dd]">
                    {photo.category}
                  </span>
                  <span className="text-sm font-extrabold text-white mt-0.5">{photo.title}</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Ribbon 2: Scrolls Right on Page Scroll */}
        <div className="relative z-10 overflow-hidden py-3 mt-2">
          <div
            data-m3-scroll-x="0.14"
            className="flex items-center gap-5 px-6 -ml-40 will-change-transform transition-transform duration-150 ease-out"
          >
            {[...GALLERY_ROW_2, ...GALLERY_ROW_2].map((photo, idx) => (
              <button
                key={`row2-${photo.src}-${idx}`}
                type="button"
                onClick={() => setSelectedPhoto(photo)}
                className="gallary-item m3-photo-card group relative shrink-0 w-[250px] sm:w-[300px] h-[200px] sm:h-[225px] rounded-[18px] border-4 border-white/15 bg-white overflow-hidden shadow-lg cursor-pointer text-left focus:outline-none focus:ring-2 focus:ring-[#16c0dd]"
              >
                <img
                  src={photo.src}
                  alt={photo.title}
                  className="h-full w-full object-cover group-hover:scale-110 transition-transform duration-500"
                />
                <div className="absolute inset-0 bg-[#191919]/60 opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex flex-col justify-end p-4">
                  <span className="text-[10px] font-extrabold uppercase tracking-widest text-[#16c0dd]">
                    {photo.category}
                  </span>
                  <span className="text-sm font-extrabold text-white mt-0.5">{photo.title}</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Lightbox Modal when user clicks a gallery photo */}
        {selectedPhoto && (
          <div
            role="dialog"
            aria-modal="true"
            aria-label={selectedPhoto.title}
            onClick={() => setSelectedPhoto(null)}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4"
          >
            <div
              onClick={(e) => e.stopPropagation()}
              className="relative max-w-2xl w-full rounded-[24px] border-8 border-white bg-white p-4 shadow-2xl overflow-hidden"
            >
              <button
                type="button"
                onClick={() => setSelectedPhoto(null)}
                className="absolute top-4 right-4 z-10 h-10 w-10 rounded-full bg-[#191919] text-white font-bold hover:bg-[#16c0dd] hover:text-[#191919] transition-colors cursor-pointer"
                aria-label="Fechar visualização"
              >
                ✕
              </button>
              <div className="h-[340px] sm:h-[420px] w-full overflow-hidden rounded-xl bg-[#f6f6f6]">
                <img
                  src={selectedPhoto.src}
                  alt={selectedPhoto.title}
                  className="h-full w-full object-contain"
                />
              </div>
              <div className="mt-4 flex items-center justify-between px-2">
                <div>
                  <span className="text-xs font-extrabold uppercase tracking-widest text-[#16c0dd]">
                    {selectedPhoto.category}
                  </span>
                  <h3 className="text-xl font-extrabold text-[#191919]">{selectedPhoto.title}</h3>
                </div>
                <Link
                  href="/produtos"
                  className="tl-primary-btn"
                  onClick={() => setSelectedPhoto(null)}
                >
                  <span>Ver no Catálogo</span>
                  <span className="icon" aria-hidden="true">
                    ↗
                  </span>
                </Link>
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
