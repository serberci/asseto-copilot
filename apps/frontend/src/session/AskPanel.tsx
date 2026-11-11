import { useState } from "react";
import { ask, type Answer } from "@/api";
import { Answer as AnswerText, Form, Section, TextInput, errorMessage } from "@/ui";

export function AskPanel({
  sessionId,
  onError,
}: {
  sessionId: string | null;
  onError: (message: string | null) => void;
}) {
  const [question, setQuestion] = useState("where am I losing time");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [asking, setAsking] = useState(false);

  async function submit() {
    if (!sessionId) return;
    setAsking(true);
    try {
      setAnswer(await ask(sessionId, question));
      onError(null);
    } catch (reason) {
      onError(errorMessage(reason, "The question failed."));
    } finally {
      setAsking(false);
    }
  }

  return (
    <Section title="Ask">
      <Form kind="ask" onSubmit={submit}>
        <TextInput value={question} onChange={setQuestion} disabled={!sessionId} />
        <button type="submit" disabled={!sessionId || asking}>
          {asking ? "Asking" : "Ask"}
        </button>
      </Form>
      {answer ? <AnswerText note={answer.model}>{answer.spoken_response}</AnswerText> : null}
    </Section>
  );
}
