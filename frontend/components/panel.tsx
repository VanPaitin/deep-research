import { ReactNode } from "react";

type PanelProps = {
  children: ReactNode;
  className?: string;
  label: string;
};

type PanelHeadingProps = {
  children: ReactNode;
};

export function Panel({ children, className = "", label }: PanelProps) {
  return (
    <section
      aria-label={label}
      className={[
        "flex min-h-[calc(100vh-140px)] min-w-0 flex-col rounded-lg border border-[#d8e0ea] bg-white shadow-[0_18px_45px_rgba(21,32,51,0.12)]",
        "max-[760px]:min-h-[520px]",
        className,
      ].join(" ")}
    >
      {children}
    </section>
  );
}

export function PanelHeading({ children }: PanelHeadingProps) {
  return (
    <div className="flex min-h-[58px] items-center gap-2 border-b border-[#d8e0ea] px-[18px] font-extrabold text-[#142033]">
      {children}
    </div>
  );
}
