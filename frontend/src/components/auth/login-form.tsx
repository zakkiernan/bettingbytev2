"use client";

import { useState, useTransition } from "react";
import { signIn } from "next-auth/react";
import { ArrowRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export function LoginForm() {
  const [email, setEmail] = useState("demo@bettingbyte.dev");
  const [password, setPassword] = useState("bettingbyte-demo");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  return (
    <Card className="mx-auto w-full max-w-md border-[color:var(--border-hover)] bg-[color:var(--bg-surface)]/90">
      <div className="space-y-6">
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-[color:var(--text-tertiary)]">NextAuth + FastAPI</p>
          <h2 className="mt-3 text-2xl font-semibold">Sign in to BettingByte</h2>
          <p className="mt-2 text-sm leading-6 text-[color:var(--text-secondary)]">Credentials auth is wired to the FastAPI `/api/auth/login` endpoint so frontend work can start before real auth logic lands.</p>
        </div>

        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            setErrorMessage(null);
            startTransition(async () => {
              const result = await signIn("credentials", {
                email,
                password,
                redirect: false,
                callbackUrl: "/dashboard",
              });

              if (result?.error) {
                setErrorMessage("Unable to sign in with the current mock backend response.");
                return;
              }

              window.location.href = result?.url ?? "/dashboard";
            });
          }}
        >
          <div className="space-y-2">
            <label className="text-xs uppercase tracking-[0.18em] text-[color:var(--text-tertiary)]" htmlFor="email">Email</label>
            <Input id="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
          </div>

          <div className="space-y-2">
            <label className="text-xs uppercase tracking-[0.18em] text-[color:var(--text-tertiary)]" htmlFor="password">Password</label>
            <Input id="password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </div>

          {errorMessage ? <p className="text-sm text-[color:var(--edge-negative)]">{errorMessage}</p> : null}

          <Button className="w-full" disabled={isPending} type="submit">
            {isPending ? "Signing in..." : "Enter the terminal"}
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        </form>
      </div>
    </Card>
  );
}
