import { Activity, CalendarDays, LayoutDashboard, ListOrdered, Wrench } from "lucide-react";

export const sportsNavigation = [
  { key: "nba", label: "NBA", href: "/nba/games", enabled: true },
  { key: "mlb", label: "MLB", href: "/dashboard", enabled: false },
] as const;

export const primaryNavigation = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/nba/props", label: "Board", icon: ListOrdered },
  { href: "/nba/games", label: "Games", icon: CalendarDays },
  { href: "/nba/live", label: "Live", icon: Activity },
] as const;

export const internalNavigation = [
  { href: "/internal", label: "Pipeline", icon: Wrench },
] as const;

export const quickLinks = [
  { href: "/internal", label: "Pipeline health" },
  { href: "/nba/props", label: "All signals" },
  { href: "/nba/props?recommended_only=true", label: "Recommended only" },
] as const;

export const internalNavLabels: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/nba/props": "Board",
  "/nba/games": "Games",
  "/nba/live": "Live",
  "/internal": "Pipeline",
  "/props": "Board",
  "/games": "Games",
  "/live": "Live",
};
