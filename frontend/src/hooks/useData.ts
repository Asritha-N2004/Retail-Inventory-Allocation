import { useQuery } from "@tanstack/react-query";
import { get } from "../services/api";
export function useData(path: string) {
  return useQuery({
    queryKey: [path],
    queryFn: () => get(path),
    refetchInterval: 30000,
  });
}
