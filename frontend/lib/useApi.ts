"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, apiMessage } from "@/lib/api";

export function useApiData<T>(loader: () => Promise<T>) {
  const router = useRouter();
  const [data, setData] = useState<T | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  const active = useRef(true);

  const reload = useCallback(
    () =>
      loader().then(
        (result) => {
          if (!active.current) return;
          setData(result);
          setLoaded(true);
        },
        (requestError: unknown) => {
          if (!active.current) return;
          if (requestError instanceof ApiError && requestError.status === 401) router.replace("/login");
          else setError(apiMessage(requestError));
          setLoaded(true);
        },
      ),
    [loader, router],
  );

  useEffect(() => {
    active.current = true;
    void reload();
    return () => {
      active.current = false;
    };
  }, [reload]);

  return { data, loaded, error, setError, reload };
}
