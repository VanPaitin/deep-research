import Markdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

import { Panel, PanelHeading } from "./panel";

type ReportPanelProps = {
  report: string;
};

export function ReportPanel({ report }: ReportPanelProps) {
  return (
    <Panel
      className="max-[1180px]:col-span-full max-[1180px]:min-h-[560px] max-[760px]:min-h-[560px]"
      label="Research report"
    >
      <PanelHeading>
        <span>Report</span>
      </PanelHeading>
      <article className="min-h-0 flex-1 overflow-auto bg-[#fbfcfe] p-[18px]">
        {report ? (
          <div className="prose prose-slate max-w-none prose-headings:font-extrabold prose-h1:mb-4 prose-h1:text-3xl prose-h2:mt-8 prose-h2:text-2xl prose-h3:text-xl prose-p:leading-7 prose-a:text-teal-700 prose-strong:text-slate-900">
            <Markdown remarkPlugins={[remarkBreaks, remarkGfm]}>{report}</Markdown>
          </div>
        ) : (
          <p className="m-0 text-slate-500">The final report will stream into this space.</p>
        )}
      </article>
    </Panel>
  );
}
