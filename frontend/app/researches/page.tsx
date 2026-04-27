"use client";

import { SignInButton, useAuth } from "@clerk/nextjs";
import { FileText, Loader2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { AppHeader } from "../../components/app-header";
import { ResearchSummary } from "../../lib/types";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export default function ResearchesPage() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const [researches, setResearches] = useState<ResearchSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoaded || !isSignedIn) {
      return;
    }

    let isMounted = true;

    async function loadResearches() {
      setIsLoading(true);
      setError(null);

      try {
        const token = await getToken();
        const response = await fetch(`${apiUrl}/api/reports`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          const message = await response.text();
          throw new Error(message || `Request failed with status ${response.status}`);
        }

        const data = (await response.json()) as ResearchSummary[];
        if (isMounted) {
          setResearches(data);
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

    void loadResearches();

    return () => {
      isMounted = false;
    };
  }, [getToken, isLoaded, isSignedIn]);

  return (
    <main className="min-h-screen p-6 max-[760px]:p-3.5">
      <section className="mx-auto max-w-[980px]">
        <AppHeader />

        {!isSignedIn ? (
          <section className="rounded-lg border border-[#d8e0ea] bg-white px-4 py-3.5 shadow-[0_10px_30px_rgba(15,23,42,0.06)]">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="m-0 leading-snug">
                Sign in to see your completed researches.
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
          <section className="rounded-lg border border-[#d8e0ea] bg-white shadow-[0_10px_30px_rgba(15,23,42,0.06)]">
            <div className="flex items-center justify-between gap-3 border-b border-[#d8e0ea] px-5 py-4">
              <div>
                <h2 className="m-0 text-xl leading-tight">Completed Researches</h2>
                <p className="m-0 mt-1 text-sm text-slate-500">
                  {researches.length} saved report{researches.length === 1 ? "" : "s"}
                </p>
              </div>
              <Link
                className="rounded-lg border border-teal-700 bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white no-underline hover:border-teal-800 hover:bg-teal-800"
                href="/"
              >
                New Research
              </Link>
            </div>

            {isLoading ? (
              <div className="flex min-h-[220px] items-center justify-center gap-2 text-slate-500">
                <Loader2 className="animate-spin" size={18} />
                <span>Loading researches</span>
              </div>
            ) : null}

            {error ? (
              <p className="m-5 rounded-lg border border-[#f1b9b3] bg-[#fff4f2] px-3 py-2.5 leading-snug text-[#b42318]">
                {error}
              </p>
            ) : null}

            {!isLoading && !error && researches.length === 0 ? (
              <div className="grid min-h-[220px] place-items-center p-6 text-center text-slate-500">
                <div>
                  <FileText className="mx-auto mb-3 text-teal-700" size={28} />
                  <p className="m-0">No completed researches yet.</p>
                </div>
              </div>
            ) : null}

            {!isLoading && !error && researches.length > 0 ? (
              <div className="divide-y divide-[#d8e0ea]">
                {researches.map((research) => (
                  <Link
                    className="grid gap-2 px-5 py-4 text-[#142033] no-underline hover:bg-[#f6f8fb]"
                    href={`/researches/${research.id}`}
                    key={research.id}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h3 className="m-0 text-base font-bold leading-snug">
                        {research.title || research.query}
                      </h3>
                      <time className="text-sm text-slate-500">
                        {formatDate(research.created_at)}
                      </time>
                    </div>
                    <p className="m-0 line-clamp-2 text-sm leading-6 text-slate-600">
                      {research.query}
                    </p>
                  </Link>
                ))}
              </div>
            ) : null}
          </section>
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
