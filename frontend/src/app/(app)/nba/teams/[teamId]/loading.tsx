import { Skeleton } from "@/components/ui/skeleton";

export default function TeamLoading() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-4 w-32" />
      <Skeleton className="h-24" />
      <Skeleton className="h-32" />
      <Skeleton className="h-64" />
    </div>
  );
}
