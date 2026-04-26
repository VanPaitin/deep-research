"use client";

import { FormEvent, useMemo, useRef, useState } from "react";
import { fetchEventSource } from "@microsoft/fetch-event-source";

import { AppHeader } from "../components/app-header";
import { ChatPanel } from "../components/chat-panel";
import { ReportPanel } from "../components/report-panel";
import { StatusPanel } from "../components/status-panel";
import { ApiEvent, Message } from "../lib/types";

const examples = [
  "What are the effects of AI on the software engineering industry?",
  "What are the differences between a DevOps engineer and a software engineer?",
];

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export default function Home() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [statusLog, setStatusLog] = useState<string[]>([]);
  const [report, setReport] = useState("");
  const [input, setInput] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const placeholder = useMemo(() => {
    if (messages.length === 0) {
      return "Enter a research topic";
    }
    return "Answer the question or add more direction";
  }, [messages.length]);

  async function submitMessage(message: string) {
    const trimmed = message.trim();
    if (!trimmed || isBusy) {
      return;
    }

    setInput("");
    setError(null);
    setIsBusy(true);
    setMessages((current) => [...current, { role: "user", content: trimmed }]);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await fetchEventSource(`${apiUrl}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed, session_id: sessionId }),
        signal: controller.signal,
        openWhenHidden: true,
        async onopen(response) {
          if (!response.ok) {
            throw new Error(`Request failed with status ${response.status}`);
          }
        },
        onmessage(event) {
          handleEvent(JSON.parse(event.data) as ApiEvent);
        },
        onerror(err) {
          throw err;
        },
      });
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setError((err as Error).message);
      }
    } finally {
      setIsBusy(false);
      abortRef.current = null;
    }
  }

  function handleEvent(event: ApiEvent) {
    setSessionId(event.session_id);

    if (event.type === "chat") {
      setMessages((current) => [
        ...current,
        { role: "assistant", content: event.content },
      ]);
    }

    if (event.type === "status") {
      setStatusLog((current) => [...current, event.content.trim()]);
    }

    if (event.type === "report") {
      setReport(event.content);
    }

    if (event.type === "error") {
      setError(event.content);
      setMessages((current) => [
        ...current,
        { role: "assistant", content: event.content },
      ]);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submitMessage(input);
  }

  function restart() {
    abortRef.current?.abort();
    setSessionId(null);
    setMessages([]);
    setStatusLog([]);
    setReport("");
    setInput("");
    setError(null);
    setIsBusy(false);
  }

  return (
    <main className="min-h-screen p-6 max-[760px]:p-3.5">
      <section className="mx-auto max-w-[1440px]">
        <AppHeader onRestart={restart} />

        <div className="grid items-stretch gap-4 min-[1181px]:grid-cols-[minmax(320px,420px)_minmax(260px,340px)_minmax(0,1fr)] max-[1180px]:grid-cols-[minmax(320px,420px)_minmax(0,1fr)] max-[760px]:grid-cols-1">
          <ChatPanel
            error={error}
            examples={examples}
            input={input}
            isBusy={isBusy}
            messages={messages}
            onExampleClick={(message) => void submitMessage(message)}
            onInputChange={setInput}
            onSubmit={handleSubmit}
            placeholder={placeholder}
          />
          <StatusPanel statusLog={statusLog} />
          <ReportPanel report={report} />
        </div>
      </section>
    </main>
  );
}
