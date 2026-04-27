"use client";

import { SignInButton, UserButton, useAuth } from "@clerk/nextjs";
import { RefreshCcw } from "lucide-react";

type AppHeaderProps = {
  onRestart: () => void;
};

export function AppHeader({ onRestart }: AppHeaderProps) {
  const { isSignedIn } = useAuth();

  return (
    <header className="mb-[18px] flex items-center justify-between gap-5 max-[760px]:items-start">
      <div>
        <p className="mb-1.5 text-[0.8rem] font-bold uppercase text-teal-700">
          MCP powered research
        </p>
        <h1 className="m-0 text-[clamp(2rem,4vw,3.6rem)] leading-none">
          Deep Research
        </h1>
      </div>
      <div className="flex items-center gap-2.5">
        {!isSignedIn ? (
          <SignInButton mode="modal">
            <button className="rounded-lg border border-teal-700 bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white hover:border-teal-800 hover:bg-teal-800">
              Sign in
            </button>
          </SignInButton>
        ) : (
          <UserButton />
        )}
        <button
          className="inline-flex size-11 items-center justify-center rounded-lg border border-[#d8e0ea] bg-white text-[#142033] hover:border-teal-700 hover:text-teal-700"
          onClick={onRestart}
          title="Restart"
        >
          <RefreshCcw size={18} />
        </button>
      </div>
    </header>
  );
}
