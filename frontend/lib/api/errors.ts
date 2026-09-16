/**
 * Utilitário compartilhado para extrair a mensagem de erro do corpo de uma
 * resposta HTTP não-2xx vinda do backend FastAPI.
 *
 * O FastAPI retorna `detail` de duas formas possíveis:
 * - `string`: erro "manual" (ex.: `HTTPException(detail="...")`).
 * - `array` de objetos `{ loc, msg, type }`: erro de validação do Pydantic
 *   (ex.: `RequestValidationError` em respostas 422), como os validators de
 *   `CollectionCreateRequest.chunk_size`/`chunk_overlap`,
 *   `PlaygroundSearchRequest.collection_ids` (`min_length`) ou
 *   `ActivateModelRequest.name` (`min_length`).
 *
 * Usado por `rag.ts` e `localModels.ts` para evitar duplicação.
 */

interface PydanticValidationErrorItem {
  msg?: unknown;
}

interface ErrorResponseBody {
  detail?: string | PydanticValidationErrorItem[] | unknown;
}

/** Extrai uma mensagem legível de um `detail` de erro do FastAPI/Pydantic. */
export function extrairMensagemDeDetail(detail: unknown): string | undefined {
  if (typeof detail === "string" && detail.length > 0) {
    return detail;
  }

  if (Array.isArray(detail)) {
    const mensagens = detail
      .map((item) => (item && typeof item === "object" && "msg" in item ? (item as PydanticValidationErrorItem).msg : undefined))
      .filter((msg): msg is string => typeof msg === "string" && msg.length > 0);

    if (mensagens.length > 0) {
      return mensagens.join("; ");
    }
  }

  return undefined;
}

/**
 * Lê o corpo de uma `Response` HTTP não-2xx e extrai a mensagem de erro,
 * lidando com `detail` em formato string, array de validação do Pydantic ou
 * ausente/inesperado (retorna `undefined` nesse último caso, cabendo ao
 * chamador aplicar uma mensagem de fallback).
 */
export async function extrairDetalheDeErro(response: Response): Promise<string | undefined> {
  const detail = await response
    .json()
    .then((body: ErrorResponseBody) => body.detail)
    .catch(() => undefined);

  return extrairMensagemDeDetail(detail);
}
