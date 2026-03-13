import { LoginForm } from "@/components/auth/login-form";

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,_rgba(0,212,255,0.12),_transparent_26%),linear-gradient(180deg,_#0b0e17_0%,_#121629_48%,_#0b0e17_100%)] px-4 py-10">
      <LoginForm />
    </main>
  );
}
