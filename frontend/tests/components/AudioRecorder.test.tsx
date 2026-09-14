import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AudioRecorder from "@/components/chat/AudioRecorder";

/** Dublê de `MediaRecorder` — jsdom não implementa a API real de gravação. */
class FakeMediaRecorder {
  static instances: FakeMediaRecorder[] = [];

  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  mimeType = "audio/webm";

  constructor(public stream: MediaStream) {
    FakeMediaRecorder.instances.push(this);
  }

  start() {
    // no-op: gravação "inicia" apenas do ponto de vista de estado do componente.
  }

  stop() {
    this.ondataavailable?.({ data: new Blob(["fake-audio-bytes"], { type: "audio/webm" }) });
    this.onstop?.();
  }
}

function fakeMediaStream(): MediaStream {
  return {
    getTracks: () => [{ stop: vi.fn() }],
  } as unknown as MediaStream;
}

describe("AudioRecorder", () => {
  const originalMediaRecorder = window.MediaRecorder;
  const originalMediaDevices = navigator.mediaDevices;

  beforeEach(() => {
    FakeMediaRecorder.instances = [];
    Object.defineProperty(window, "MediaRecorder", {
      configurable: true,
      value: FakeMediaRecorder,
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "MediaRecorder", {
      configurable: true,
      value: originalMediaRecorder,
    });
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: originalMediaDevices,
    });
    vi.restoreAllMocks();
  });

  it("clique inicia a gravação (muda estado visual) e clique de novo para e envia o áudio", async () => {
    const getUserMedia = vi.fn().mockResolvedValue(fakeMediaStream());
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia },
    });

    const onRecordingComplete = vi.fn();
    const onRecordingStateChange = vi.fn();
    const user = userEvent.setup();

    render(
      <AudioRecorder
        onRecordingComplete={onRecordingComplete}
        onRecordingStateChange={onRecordingStateChange}
      />,
    );

    const button = screen.getByRole("button", { name: "Gravar áudio" });
    await user.click(button);

    await waitFor(() => {
      expect(getUserMedia).toHaveBeenCalledWith({ audio: true });
    });
    expect(await screen.findByRole("button", { name: "Parar gravação" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(onRecordingStateChange).toHaveBeenCalledWith(true);

    await user.click(screen.getByRole("button", { name: "Parar gravação" }));

    await waitFor(() => {
      expect(onRecordingComplete).toHaveBeenCalledTimes(1);
    });
    // Blob → base64 sem o prefixo "data:...;base64,".
    expect(onRecordingComplete.mock.calls[0][0]).toEqual(expect.any(String));
    expect(onRecordingComplete.mock.calls[0][0].length).toBeGreaterThan(0);
    expect(onRecordingStateChange).toHaveBeenCalledWith(false);
    expect(screen.getByRole("button", { name: "Gravar áudio" })).toBeInTheDocument();
  });

  it("mostra erro claro quando a permissão de microfone é negada", async () => {
    const getUserMedia = vi.fn().mockRejectedValue(new DOMException("Permission denied"));
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia },
    });

    const onRecordingComplete = vi.fn();
    const user = userEvent.setup();

    render(<AudioRecorder onRecordingComplete={onRecordingComplete} />);

    await user.click(screen.getByRole("button", { name: "Gravar áudio" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/permissão/i);
    expect(onRecordingComplete).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Gravar áudio" })).toBeInTheDocument();
  });

  it("desabilita o botão quando o navegador não suporta gravação de áudio", () => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: undefined,
    });

    render(<AudioRecorder onRecordingComplete={vi.fn()} />);

    expect(
      screen.getByRole("button", { name: "Gravação de áudio não suportada neste navegador" }),
    ).toBeDisabled();
  });
});
