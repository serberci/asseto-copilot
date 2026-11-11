import { useState } from "react";
import { login, type Identity } from "@/api";
import { BrandHeader, ErrorText, Form, Page, TextField, errorMessage } from "@/ui";

export function Login({ onSuccess }: { onSuccess: (who: Identity) => void }) {
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    try {
      onSuccess(await login(name.trim(), password));
      setError(null);
    } catch (reason) {
      setError(errorMessage(reason, "The name or password is wrong"));
    }
  }

  return (
    <Page>
      <BrandHeader />
      <Form kind="login" onSubmit={submit}>
        <TextField label="Name" value={name} onChange={setName} autoComplete="username" />
        <TextField
          label="Password"
          value={password}
          onChange={setPassword}
          type="password"
          autoComplete="current-password"
        />
        <button type="submit">Log in</button>
        <ErrorText>{error}</ErrorText>
      </Form>
    </Page>
  );
}
