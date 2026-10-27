"use client";

import { useState, type FormEvent } from "react";
import type { ChatMessage } from "@/lib/boardApi";

type BoardChatProps = {
  onSend: (question: string, history: ChatMessage[]) => Promise<string>;
};

export const BoardChat = ({ onSend }: BoardChatProps) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = question.trim();
    if (!message || sending) {
      return;
    }

    setSending(true);
    setError(null);
    try {
      const reply = await onSend(message, messages);
      setMessages([
        ...messages,
        { role: "user", content: message },
        { role: "assistant", content: reply },
      ]);
      setQuestion("");
    } catch (sendError) {
      setError(
        sendError instanceof Error
          ? sendError.message
          : "Unable to send your message."
      );
    } finally {
      setSending(false);
    }
  };

  return (
    <aside
      aria-label="AI board assistant"
      className="flex min-h-[520px] flex-col rounded-3xl border border-[var(--stroke)] bg-white p-5 shadow-[var(--shadow)]"
    >
      <div className="border-b border-[var(--stroke)] pb-4">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--primary-blue)]">
          Board assistant
        </p>
        <h2 className="mt-2 font-display text-xl font-semibold text-[var(--navy-dark)]">
          Ask about your project
        </h2>
        <p className="mt-2 text-sm leading-6 text-[var(--gray-text)]">
          Ask a question or request a board update.
        </p>
      </div>

      <div
        role="log"
        aria-label="Conversation"
        aria-live="polite"
        className="flex-1 space-y-4 overflow-y-auto py-5"
      >
        {messages.length === 0 ? (
          <p className="text-sm leading-6 text-[var(--gray-text)]">
            Your assistant can review the board and make card or column changes.
          </p>
        ) : (
          messages.map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              className={
                message.role === "user"
                  ? "ml-5 rounded-2xl bg-[var(--surface)] px-4 py-3 text-sm text-[var(--navy-dark)]"
                  : "mr-3 rounded-2xl border border-[var(--stroke)] px-4 py-3 text-sm leading-6 text-[var(--navy-dark)]"
              }
            >
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.15em] text-[var(--gray-text)]">
                {message.role === "user" ? "You" : "Assistant"}
              </p>
              <p className="whitespace-pre-wrap">{message.content}</p>
            </div>
          ))
        )}
        {sending && (
          <p role="status" className="text-sm text-[var(--gray-text)]">
            Assistant is thinking...
          </p>
        )}
      </div>

      {error && (
        <p role="alert" className="mb-3 text-sm text-red-700">
          {error}
        </p>
      )}
      <form onSubmit={handleSubmit} className="space-y-3 border-t border-[var(--stroke)] pt-4">
        <label
          htmlFor="board-chat-message"
          className="sr-only"
        >
          Message the board assistant
        </label>
        <textarea
          id="board-chat-message"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask a question or request a change..."
          rows={3}
          maxLength={4000}
          disabled={sending}
          className="w-full resize-y rounded-2xl border border-[var(--stroke)] bg-white px-4 py-3 text-sm text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)] disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={sending || !question.trim()}
          className="w-full rounded-full bg-[var(--secondary-purple)] px-4 py-3 text-sm font-semibold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {sending ? "Sending..." : "Send"}
        </button>
      </form>
    </aside>
  );
};
