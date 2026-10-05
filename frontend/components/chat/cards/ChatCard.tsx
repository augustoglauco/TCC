import type { ChatCard as ChatCardData } from "@/lib/types/chat";
import AppointmentCard from "@/components/chat/cards/AppointmentCard";
import ChatChartCard from "@/components/chat/cards/ChatChartCard";
import DocumentDownloadCard from "@/components/chat/cards/DocumentDownloadCard";
import ProductCard from "@/components/chat/cards/ProductCard";
import QuoteCard from "@/components/chat/cards/QuoteCard";

/** Despacha para o card certo conforme `card.tipo` (Fase 8) — usado pelo
 * `MessageBubble` para renderizar o card junto da resposta do assistente. */
export default function ChatCard({ card }: { card: ChatCardData }) {
  switch (card.tipo) {
    case "produto":
      return <ProductCard card={card} />;
    case "cotacao":
      return <QuoteCard card={card} />;
    case "agendamento":
      return <AppointmentCard card={card} />;
    case "grafico":
      return <ChatChartCard card={card} />;
    case "documento_download":
      return <DocumentDownloadCard card={card} />;
    default:
      return null;
  }
}
