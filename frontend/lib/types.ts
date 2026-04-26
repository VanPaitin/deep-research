export type ApiEvent = {
  type: "session" | "chat" | "status" | "report" | "error" | "done";
  content: string;
  session_id: string;
};

export type Message = {
  role: "assistant" | "user";
  content: string;
};
