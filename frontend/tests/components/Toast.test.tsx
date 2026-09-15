import { act, render, renderHook, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ToastStack, useToast } from "@/components/ui/Toast";

describe("useToast/ToastStack", () => {
  it("adiciona um toast e renderiza a mensagem", () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.showToast("Documento excluído.", "success");
    });

    render(<ToastStack toasts={result.current.toasts} onDismiss={() => {}} />);

    expect(screen.getByText("Documento excluído.")).toBeInTheDocument();
  });

  it("remove o toast ao chamar dismissToast", () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.showToast("Erro ao excluir.", "error");
    });
    const [toast] = result.current.toasts;

    act(() => {
      result.current.dismissToast(toast.id);
    });

    expect(result.current.toasts).toHaveLength(0);
  });
});
