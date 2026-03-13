import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

export const { handlers, signIn, signOut, auth } = NextAuth({
  pages: {
    signIn: "/login",
  },
  session: {
    strategy: "jwt",
  },
  providers: [
    Credentials({
      name: "Credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials.password) {
          return null;
        }

        const response = await fetch(`${apiBaseUrl}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: credentials.email,
            password: credentials.password,
          }),
        });

        if (!response.ok) {
          return null;
        }

        const payload = (await response.json()) as {
          token: string;
          user: { id: number; email: string; tier: string };
        };

        return {
          id: String(payload.user.id),
          email: payload.user.email,
          tier: payload.user.tier,
          accessToken: payload.token,
        };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.tier = user.tier;
        token.accessToken = user.accessToken;
      }

      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.sub ?? "";
        session.user.tier = typeof token.tier === "string" ? token.tier : "FREE";
      }
      session.accessToken = typeof token.accessToken === "string" ? token.accessToken : undefined;
      return session;
    },
  },
});
