export { auth as middleware } from "@/auth";

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/props/:path*",
    "/player/:path*",
    "/live/:path*",
    "/picks/:path*",
    "/community/:path*",
    "/alerts/:path*",
    "/settings/:path*",
  ],
};
