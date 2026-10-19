import { QueryClient } from "@tanstack/react-query";
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30000, retry: 1, refetchOnWindowFocus: true },
  },
});

import type { User } from "../types";
export function hydrateUser(client: QueryClient, user: User): void {
  client.setQueryData(["me"], user);
  for (const member of user.memberships)
    if (member.config)
      client.setQueryData(["config", member.id], member.config);
}
