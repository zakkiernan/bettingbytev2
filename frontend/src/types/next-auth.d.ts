import type { DefaultSession } from "next-auth";

declare module "next-auth" {
  interface Session {
    accessToken?: string;
    user: DefaultSession["user"] & {
      id: string;
      tier: string;
    };
  }

  interface User {
    tier?: string;
    accessToken?: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    tier?: string;
    accessToken?: string;
  }
}
