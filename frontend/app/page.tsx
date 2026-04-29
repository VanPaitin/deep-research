"use client";

import { FormEvent, useMemo, useRef, useState } from "react";
import { SignInButton, useAuth } from "@clerk/nextjs";
import { fetchEventSource } from "@microsoft/fetch-event-source";

import { AppHeader } from "../components/app-header";
import { ChatPanel } from "../components/chat-panel";
import { ReportPanel } from "../components/report-panel";
import { StatusPanel } from "../components/status-panel";
import { ApiEvent, Message, ResearchJobResponse } from "../lib/types";

const examples = [
  "What are the effects of AI on the software engineering industry?",
  "What are the differences between a DevOps engineer and a software engineer?",
];

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export default function Home() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const [jobId, setJobId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [statusLog, setStatusLog] = useState<string[]>([]);
  const [report, setReport] = useState("");
  const [input, setInput] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const lastSequenceRef = useRef(0);

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

    if (!isLoaded || !isSignedIn) {
      setError("Sign in to save and run research reports.");
      return;
    }

    const token = await getToken();
    if (!token) {
      setError("Could not read your sign-in session. Please sign in again.");
      return;
    }

    setInput("");
    setError(null);
    setIsBusy(true);
    setMessages((current) => [...current, { role: "user", content: trimmed }]);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await fetch(
        jobId ? `${apiUrl}/api/research-jobs/${jobId}/messages` : `${apiUrl}/api/research-jobs`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(jobId ? { message: trimmed } : { query: trimmed }),
          signal: controller.signal,
        },
      );

      if (!response.ok) {
        throw new Error(await readError(response));
      }

      const data = await readJson<ResearchJobResponse>(response);
      setJobId(data.id);
      data.events.forEach(handleEvent);

      if (data.status === "running") {
        await streamJob(data.id, token, lastSequenceRef.current);
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setError((err as Error).message);
      }
    } finally {
      setIsBusy(false);
      abortRef.current = null;
    }
  }

  async function streamJob(id: string, token: string, after: number): Promise<void> {
    let shouldReconnect = false;
    const controller = new AbortController();
    abortRef.current = controller;

    await fetchEventSource(`${apiUrl}/api/research-jobs/${id}/stream?after=${after}`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      signal: controller.signal,
      openWhenHidden: true,
      async onopen(response) {
        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }
      },
      onmessage(event) {
        if (!event.data.trim()) {
          return;
        }
        const parsed = JSON.parse(event.data) as ApiEvent;
        if (parsed.type === "reconnect") {
          shouldReconnect = true;
          return;
        }
        handleEvent(parsed);
      },
      onerror(err) {
        throw err;
      },
    });

    if (shouldReconnect && !controller.signal.aborted) {
      await streamJob(id, token, lastSequenceRef.current);
    }
  }

  function handleEvent(event: ApiEvent) {
    if (typeof event.sequence === "number") {
      lastSequenceRef.current = Math.max(lastSequenceRef.current, event.sequence);
    }

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
    setJobId(null);
    lastSequenceRef.current = 0;
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

        {!isSignedIn ? (
          <section className="mb-4 rounded-lg border border-[#d8e0ea] bg-white px-4 py-3.5 text-[#142033] shadow-[0_10px_30px_rgba(15,23,42,0.06)]">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="m-0 leading-snug">
                Sign in to run research and save completed reports.
              </p>
              <SignInButton mode="modal">
                <button className="rounded-lg border border-teal-700 bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white hover:border-teal-800 hover:bg-teal-800">
                  Sign in
                </button>
              </SignInButton>
            </div>
          </section>
        ) : null}

        {isSignedIn ? (
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
        ) : null}
      </section>
    </main>
  );
}

async function readError(response: Response) {
  const text = await response.text();
  if (!text) {
    return `Request failed with status ${response.status}`;
  }

  try {
    const parsed = JSON.parse(text) as { detail?: string };
    return parsed.detail || text;
  } catch {
    return text;
  }
}

async function readJson<T>(response: Response): Promise<T> {
  const text = await response.text();
  if (!text.trim()) {
    throw new Error("The server returned an empty response.");
  }

  return JSON.parse(text) as T;
}
