import { Panel, PanelHeading } from "./panel";

type StatusPanelProps = {
  statusLog: string[];
};

export function StatusPanel({ statusLog }: StatusPanelProps) {
  return (
    <Panel label="Research status">
      <PanelHeading>
        <span>Status</span>
      </PanelHeading>
      <div className="flex min-h-0 flex-1 flex-col gap-2.5 overflow-auto bg-[#fbfcfe] p-[18px]">
        {statusLog.length === 0 ? (
          <p className="m-0 text-slate-500">Progress updates will appear here.</p>
        ) : (
          statusLog.map((item, index) => (
            <p
              className="m-0 border-l-[3px] border-teal-700 py-1 pl-2.5 leading-snug text-slate-700"
              key={`${item}-${index}`}
            >
              {item}
            </p>
          ))
        )}
      </div>
    </Panel>
  );
}
