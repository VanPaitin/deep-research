"use client";

import { SignInButton, useAuth } from "@clerk/nextjs";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";
import { use, useEffect, useState } from "react";
import Markdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

import { AppHeader } from "../../../components/app-header";
import { ResearchDetail } from "../../../lib/types";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type ResearchPageProps = {
  params: Promise<{ id: string }>;
};

export default function ResearchPage({ params }: ResearchPageProps) {
  const { id: researchId } = use(params);
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const [research, setResearch] = useState<ResearchDetail | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoaded || !isSignedIn) {
      return;
    }

    let isMounted = true;

    async function loadResearch() {
      setIsLoading(true);
      setError(null);

      try {
        const token = await getToken();
        const response = await fetch(`${apiUrl}/api/reports/${researchId}`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          const message = await response.text();
          throw new Error(message || `Request failed with status ${response.status}`);
        }

        const data = (await response.json()) as ResearchDetail;
        if (isMounted) {
          setResearch(data);
        }
      } catch (err) {
        if (isMounted) {
          setError((err as Error).message);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadResearch();

    return () => {
      isMounted = false;
    };
  }, [getToken, isLoaded, isSignedIn, researchId]);

  return (
    <main className="min-h-screen p-6 max-[760px]:p-3.5">
      <section className="mx-auto max-w-[1040px]">
        <AppHeader />

        {!isSignedIn ? (
          <section className="rounded-lg border border-[#d8e0ea] bg-white px-4 py-3.5 shadow-[0_10px_30px_rgba(15,23,42,0.06)]">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="m-0 leading-snug">
                Sign in to open this research.
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
          <article className="rounded-lg border border-[#d8e0ea] bg-white shadow-[0_10px_30px_rgba(15,23,42,0.06)]">
            <header className="border-b border-[#d8e0ea] px-5 py-4">
              <Link
                className="mb-4 inline-flex items-center gap-2 text-sm font-semibold text-teal-700 no-underline hover:text-teal-900"
                href="/researches"
              >
                <ArrowLeft size={16} />
                Researches
              </Link>

              {research ? (
                <div>
                  <h2 className="m-0 text-2xl leading-tight">
                    {research.title || research.query}
                  </h2>
                  <p className="m-0 mt-2 text-sm leading-6 text-slate-500">
                    {research.query}
                  </p>
                  <time className="mt-3 block text-sm text-slate-500">
                    {formatDate(research.created_at)}
                  </time>
                </div>
              ) : null}
            </header>

            {isLoading ? (
              <div className="flex min-h-[320px] items-center justify-center gap-2 text-slate-500">
                <Loader2 className="animate-spin" size={18} />
                <span>Loading research</span>
              </div>
            ) : null}

            {error ? (
              <p className="m-5 rounded-lg border border-[#f1b9b3] bg-[#fff4f2] px-3 py-2.5 leading-snug text-[#b42318]">
                {error}
              </p>
            ) : null}

            {!isLoading && !error && research ? (
              <div className="grid gap-6 p-5">
                <section className="rounded-lg border border-[#d8e0ea] bg-[#f6f8fb] p-4">
                  <h3 className="m-0 mb-3 text-base">Research Brief</h3>
                  <div className="grid gap-3">
                    {research.clarifying_questions.map((question, index) => (
                      <div className="grid gap-1" key={`${question}-${index}`}>
                        <p className="m-0 text-sm font-semibold text-[#142033]">
                          {question}
                        </p>
                        <p className="m-0 text-sm leading-6 text-slate-600">
                          {research.clarifying_answers[index] || ""}
                        </p>
                      </div>
                    ))}
                  </div>
                </section>

                <section className="prose prose-slate max-w-none prose-headings:font-extrabold prose-h1:mb-4 prose-h1:text-3xl prose-h2:mt-8 prose-h2:text-2xl prose-h3:text-xl prose-p:leading-7 prose-a:text-teal-700 prose-strong:text-slate-900">
                  <Markdown remarkPlugins={[remarkBreaks, remarkGfm]}>
                    {research.content_markdown}
                  </Markdown>
                </section>
              </div>
            ) : null}
          </article>
        ) : null}
      </section>
    </main>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
