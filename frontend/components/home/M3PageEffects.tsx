"use client";

import { useEffect, useState } from "react";

export default function M3PageEffects() {
  const [preloaderStep, setPreloaderStep] = useState<"bars" | "fade" | "done">("bars");
  const [scrollPct, setScrollPct] = useState(0);
  const [showScrollBtn, setShowScrollBtn] = useState(false);

  // 1. Preloader de 8 barras verticais (portado de m3glass.com/assets/js/main.js)
  useEffect(() => {
    const t1 = window.setTimeout(() => setPreloaderStep("fade"), 450);
    const t2 = window.setTimeout(() => setPreloaderStep("done"), 950);
    return () => {
      window.clearTimeout(t1);
      window.clearTimeout(t2);
    };
  }, []);

  // 2. Scroll-Reveal ([data-m3-reveal]) + Scroll-Scrubbing ([data-m3-scroll-x])
  useEffect(() => {
    const revealEls = Array.from(document.querySelectorAll<HTMLElement>("[data-m3-reveal]"));

    if (typeof IntersectionObserver !== "undefined" && revealEls.length > 0) {
      revealEls.forEach((el) => {
        const rect = el.getBoundingClientRect();
        if (rect.top > window.innerHeight * 0.92) {
          el.classList.add("m3-pending");
        } else {
          el.classList.add("m3-visible");
        }
      });

      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              const target = entry.target as HTMLElement;
              const delay = target.dataset.m3Delay || "0ms";
              target.style.transitionDelay = delay;
              target.classList.remove("m3-pending");
              target.classList.add("m3-visible");
              observer.unobserve(target);
            }
          });
        },
        { threshold: 0.12, rootMargin: "0px 0px -40px 0px" },
      );

      revealEls.forEach((el) => observer.observe(el));

      return () => observer.disconnect();
    }
  }, []);

  // 3. Indicador circular de percentual de rolagem (#scroll-percentage) + Parallax X
  useEffect(() => {
    const handleScroll = () => {
      const scrollTop = window.scrollY || document.documentElement.scrollTop;
      const calcHeight =
        document.documentElement.scrollHeight - document.documentElement.clientHeight;
      const pct =
        calcHeight > 0 ? Math.min(100, Math.max(0, Math.round((scrollTop / calcHeight) * 100))) : 0;

      setScrollPct(pct);
      setShowScrollBtn(scrollTop > 120);

      // Scrubbing horizontal nas faixas [data-m3-scroll-x] (gallaryScroll / scroll-area)
      const scrubEls = document.querySelectorAll<HTMLElement>("[data-m3-scroll-x]");
      scrubEls.forEach((el) => {
        const factor = parseFloat(el.dataset.m3ScrollX || "-0.18");
        const rect = el.getBoundingClientRect();
        const progress = window.innerHeight - rect.top;
        const offset = progress * factor;
        el.style.transform = `translate3d(${offset.toFixed(1)}px, 0, 0)`;
      });
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <>
      {/* Cortina Preloader de 8 Barras Verticais estilo M3 Glass */}
      {preloaderStep !== "done" && (
        <div
          aria-hidden="true"
          className={`pointer-events-none fixed inset-0 z-50 flex items-center justify-center bg-[#111111] transition-opacity duration-500 ${
            preloaderStep === "fade" ? "opacity-0" : "opacity-100"
          }`}
        >
          <div className="relative z-20 px-6 text-center">
            <span className="block text-[11px] font-mono uppercase tracking-[0.35em] text-[#16c0dd] mb-2">
              Fictícia • IA Multimodal • MCP B2B
            </span>
            <span className="text-2xl sm:text-5xl lg:text-6xl font-extrabold uppercase tracking-wider text-white">
              Design, meet Security
            </span>
          </div>
          <div className="absolute inset-0 z-10 flex">
            {[0, 1, 2, 3, 4, 5, 6, 7].map((barIdx) => (
              <div
                key={barIdx}
                className="relative h-full w-[12.5%] overflow-hidden border-r border-white/5"
              >
                <div
                  className="h-full bg-white/10 transition-all duration-500 ease-out"
                  style={{
                    width: preloaderStep === "bars" ? "45%" : "100%",
                    transitionDelay: `${barIdx * 35}ms`,
                  }}
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Botão Circular de Percentual de Rolagem (#scroll-percentage de m3glass.com) */}
      <button
        type="button"
        onClick={scrollToTop}
        aria-label="Voltar ao topo da página"
        style={{
          background: `conic-gradient(#16c0dd ${scrollPct}%, rgba(25, 25, 25, 0.25) ${scrollPct}%)`,
        }}
        className={`fixed bottom-6 left-6 z-40 grid h-14 w-14 place-items-center rounded-full p-[3px] shadow-[0_11px_41px_3px_rgba(22,192,221,0.22)] transition-all duration-300 cursor-pointer ${
          showScrollBtn
            ? "scale-100 opacity-100 visible translate-y-0"
            : "scale-0 opacity-0 invisible translate-y-4 pointer-events-none"
        }`}
      >
        <span className="grid h-full w-full place-items-center rounded-full bg-slate-950 text-xs font-extrabold text-[#16c0dd]">
          {scrollPct < 96 ? `${scrollPct}%` : "↑"}
        </span>
      </button>
    </>
  );
}
