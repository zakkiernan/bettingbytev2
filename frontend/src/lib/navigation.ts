import {
  Activity,
  BarChart3,
  Bell,
  Gauge,
  LayoutDashboard,
  ListOrdered,
  Settings,
  Trophy,
  Users,
} from "lucide-react";

export const primaryNavigation = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/props", label: "Props", icon: ListOrdered },
  { href: "/live", label: "Live", icon: Activity },
  { href: "/picks", label: "Picks", icon: Trophy },
  { href: "/community", label: "Community", icon: Users },
  { href: "/alerts", label: "Alerts", icon: Bell },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;

export const quickLinks = [
  { href: "/props/1", label: "Prop Detail" },
  { href: "/player/2544", label: "Player Profile" },
  { href: "/live/0022500099", label: "Live Drilldown" },
  { href: "/community/leaderboard", label: "Leaderboard" },
  { href: "/picks/history", label: "Pick History" },
] as const;

export const dashboardMetrics = [
  { label: "Slate games", value: "6", icon: Gauge },
  { label: "Tracked props", value: "47", icon: BarChart3 },
  { label: "Live alerts", value: "3", icon: Bell },
] as const;
