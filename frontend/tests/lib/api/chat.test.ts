import { describe, expect, it, vi } from "vitest";

import { sendChatMessage } from "@/lib/api/chat";

function sseStream(blocks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let i = 0;
  return new ReadableStream({
    pull(controller) {
      if (i < blocks.length) {
        controller.enqueue(encoder.encode(blocks[i]));
        i += 1;
      } else {
        controller.close();
      }
    },
  });
}

function mockFetchOnce(body: ReadableStream<Uint8Array>, ok = true, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok,
      status,
      body,
    } as Response),
  );
}

describe("sendChatMessage", () => {
  it("chama os callbacks na ordem certa pra um fluxo de texto simples", async () => {
    mockFetchOnce(
      sseStream([
        'event: conversation\ndata: {"conversation_id":"conv-1"}\n\n',
        'event: token\ndata: {"text":"Olá"}\n\n',
        'event: token\ndata: {"text":", tudo bem?"}\n\n',
        'event: done\ndata: {"domain":"vendas","backend_used":"local","escalation_reason":"nenhum"}\n\n',
      ]),
    );

    const onConversationId = vi.fn();
    const onToken = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();

    await sendChatMessage({
      message: "oi",
      onConversationId,
      onTranscription: vi.fn(),
      onStatus: vi.fn(),
      onToken,
      onDone,
      onError,
    });

    expect(onConversationId).toHaveBeenCalledWith("conv-1");
    expect(onToken).toHaveBeenNthCalledWith(1, "Olá");
    expect(onToken).toHaveBeenNthCalledWith(2, ", tudo bem?");
    expect(onDone).toHaveBeenCalledWith(
      expect.objectContaining({ domain: "vendas", backend_used: "local" }),
    );
    expect(onError).not.toHaveBeenCalled();
  });

  it("chama onStatus quando o evento status chega antes dos tokens", async () => {
    mockFetchOnce(
      sseStream([
        'event: conversation\ndata: {"conversation_id":"conv-1"}\n\n',
        'event: status\ndata: {"status":"carregando_modelo"}\n\n',
        'event: token\ndata: {"text":"ok"}\n\n',
        'event: done\ndata: {"domain":"vendas","backend_used":"local","escalation_reason":"nenhum"}\n\n',
      ]),
    );

    const onStatus = vi.fn();
    await sendChatMessage({
      message: "oi",
      onConversationId: vi.fn(),
      onTranscription: vi.fn(),
      onStatus,
      onToken: vi.fn(),
      onDone: vi.fn(),
      onError: vi.fn(),
    });

    expect(onStatus).toHaveBeenCalledWith("carregando_modelo");
  });

  it("chama onError quando o evento error chega", async () => {
    mockFetchOnce(
      sseStream([
        'event: conversation\ndata: {"conversation_id":"conv-1"}\n\n',
        'event: error\ndata: {"detail":"Serviço temporariamente indisponível, tente novamente."}\n\n',
      ]),
    );

    const onError = vi.fn();
    await sendChatMessage({
      message: "oi",
      onConversationId: vi.fn(),
      onTranscription: vi.fn(),
      onStatus: vi.fn(),
      onToken: vi.fn(),
      onDone: vi.fn(),
      onError,
    });

    expect(onError).toHaveBeenCalledWith("Serviço temporariamente indisponível, tente novamente.");
  });

  it("chama onError quando o fetch falha (rede)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );

    const onError = vi.fn();
    await sendChatMessage({
      message: "oi",
      onConversationId: vi.fn(),
      onTranscription: vi.fn(),
      onStatus: vi.fn(),
      onToken: vi.fn(),
      onDone: vi.fn(),
      onError,
    });

    expect(onError).toHaveBeenCalledWith("Não foi possível conectar ao servidor. Verifique sua conexão.");
  });

  it("chama onError quando a resposta HTTP não é 2xx", async () => {
    mockFetchOnce(sseStream([]), false, 503);

    const onError = vi.fn();
    await sendChatMessage({
      message: "oi",
      onConversationId: vi.fn(),
      onTranscription: vi.fn(),
      onStatus: vi.fn(),
      onToken: vi.fn(),
      onDone: vi.fn(),
      onError,
    });

    expect(onError).toHaveBeenCalledWith("Serviço temporariamente indisponível. Tente novamente.");
  });
});
