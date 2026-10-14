"use client";

import { useSyncExternalStore } from "react";

function subscribeNoop() {
  return () => {};
}

// Detecta "ja hidratou no cliente" sem `useState`+`useEffect` —
// useSyncExternalStore e o jeito recomendado pelo React para esse caso
// especifico (retorna o snapshot do servidor ate hidratar, depois o do
// cliente, sem o setState sincrono dentro de efeito que a regra
// react-hooks/set-state-in-effect reclamaria, e sem o segundo render que
// esse setState causava).
export function useEstaNoCliente(): boolean {
  return useSyncExternalStore(
    subscribeNoop,
    () => true,
    () => false,
  );
}
