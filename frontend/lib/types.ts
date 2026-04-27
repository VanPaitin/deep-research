export type ApiEvent = {
  type: "session" | "chat" | "status" | "report" | "error" | "done";
  content: string;
  session_id: string;
};

export type Message = {
  role: "assistant" | "user";
  content: string;
};

export type ResearchSummary = {
  id: string;
  title: string | null;
  query: string;
  created_at: string;
  updated_at: string;
};

export type ResearchDetail = ResearchSummary & {
  clarifying_questions: string[];
  clarifying_answers: string[];
  content_markdown: string;
};
