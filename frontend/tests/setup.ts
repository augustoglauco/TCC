import "@testing-library/jest-dom/vitest";

// jsdom não implementa navegação: clicar em <a href> real imprime "Not implemented:
// navigation" no stderr. Cancelamos o clique padrão na captura (o handler do componente
// pode desmontar o link antes de o evento subir) sem afetar os handlers.
document.addEventListener(
  "click",
  (event) => {
    const link = (event.target as Element | null)?.closest?.("a[href]");
    const href = link?.getAttribute("href");
    if (href && !href.startsWith("#")) event.preventDefault();
  },
  true,
);
