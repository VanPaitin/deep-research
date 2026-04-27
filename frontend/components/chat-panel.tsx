"use client";

import { FormEvent, useEffect, useRef } from "react";
import { Send, Sparkles } from "lucide-react";

import { Message } from "../lib/types";
import { Panel, PanelHeading } from "./panel";

type ChatPanelProps = {
  error: string | null;
  examples: string[];
  input: string;
  isBusy: boolean;
  messages: Message[];
  placeholder: string;
  onInputChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onExampleClick: (message: string) => void;
};

export function ChatPanel({
  error,
  examples,
  input,
  isBusy,
  messages,
  placeholder,
  onInputChange,
  onSubmit,
  onExampleClick,
}: ChatPanelProps) {
  const messagesRef = useRef<HTMLDivElement | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const shouldFollowRef = useRef(true);

  useEffect(() => {
    if (shouldFollowRef.current) {
      bottomRef.current?.scrollIntoView({ block: "end" });
    }
  }, [messages]);

  useEffect(() => {
    const lastMessage = messages.at(-1);

    if (!isBusy && lastMessage?.role === "assistant") {
      inputRef.current?.focus();
    }
  }, [isBusy, messages]);

  function handleMessagesScroll() {
    const element = messagesRef.current;

    if (!element) {
      return;
    }

    const distanceFromBottom =
      element.scrollHeight - element.scrollTop - element.clientHeight;
    shouldFollowRef.current = distanceFromBottom < 80;
  }

  return (
    <Panel label="Research chat">
      <PanelHeading>
        <Sparkles size={18} />
        <span>Research brief</span>
      </PanelHeading>

      <div
        className="flex min-h-0 flex-1 flex-col gap-3 overflow-auto p-[18px]"
        onScroll={handleMessagesScroll}
        ref={messagesRef}
      >
        {messages.length === 0 ? (
          <EmptyChat examples={examples} onExampleClick={onExampleClick} />
        ) : (
          messages.map((message, index) => (
            <MessageBubble
              key={`${message.role}-${index}`}
              message={message}
            />
          ))
        )}
        <div ref={bottomRef} />
      </div>

      {error ? (
        <p className="mx-3.5 mb-3 mt-0 rounded-lg border border-[#f1b9b3] bg-[#fff4f2] px-3 py-2.5 leading-snug text-[#b42318]">
          {error}
        </p>
      ) : null}

      <form
        className="grid grid-cols-[1fr_44px] gap-2.5 border-t border-[#d8e0ea] p-3.5"
        onSubmit={onSubmit}
      >
        <textarea
          aria-label="Message"
          className="min-h-11 max-h-[150px] resize-y rounded-lg border border-[#d8e0ea] px-3 py-[11px] text-[#142033] outline-none focus:border-teal-700 focus:shadow-[0_0_0_3px_rgba(15,118,110,0.12)] disabled:cursor-not-allowed disabled:opacity-55"
          disabled={isBusy}
          onChange={(event) => onInputChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              event.currentTarget.form?.requestSubmit();
            }
          }}
          placeholder={placeholder}
          ref={inputRef}
          value={input}
        />
        <button
          className="inline-flex size-11 self-end items-center justify-center rounded-lg border border-teal-700 bg-teal-700 text-white hover:border-teal-700 hover:text-white disabled:cursor-not-allowed disabled:opacity-55"
          disabled={isBusy || !input.trim()}
          type="submit"
          title="Send"
        >
          <Send size={18} />
        </button>
      </form>
    </Panel>
  );
}

function EmptyChat({
  examples,
  onExampleClick,
}: {
  examples: string[];
  onExampleClick: (message: string) => void;
}) {
  return (
    <div className="grid gap-4 leading-[1.55] text-slate-500">
      <p className="m-0">
        Start with a topic. The agent will ask three quick questions before researching.
      </p>
      <div className="grid gap-2.5">
        {examples.map((example) => (
          <button
            className="w-full rounded-lg border border-[#d8e0ea] bg-[#f6f8fb] p-3 text-left leading-snug text-[#142033] hover:border-teal-700"
            key={example}
            onClick={() => onExampleClick(example)}
          >
            {example}
          </button>
        ))}
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  return (
    <article
      className={[
        "max-w-[92%] whitespace-pre-wrap rounded-lg border border-[#d8e0ea] px-3.5 py-3 leading-[1.55]",
        message.role === "user"
          ? "self-end border-[#b9d5d1] bg-[#e8f5f3]"
          : "self-start bg-[#f6f8fb]",
      ].join(" ")}
    >
      {message.content}
    </article>
  );
}
