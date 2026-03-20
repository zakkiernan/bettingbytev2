import { Activity, CalendarDays, LayoutDashboard, ListOrdered } from "lucide-react";

export const primaryNavigation = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/props", label: "Board", icon: ListOrdered },
  { href: "/games", label: "Games", icon: CalendarDays },
  { href: "/live", label: "Live", icon: Activity },
] as const;

export const quickLinks = [
  { href: "/dashboard", label: "Pipeline health" },
  { href: "/props", label: "All signals" },
  { href: "/props?recommended_only=true", label: "Recommended only" },
] as const;

export const internalNavLabels: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/props": "Board",
  "/games": "Games",
  "/live": "Live",
};
