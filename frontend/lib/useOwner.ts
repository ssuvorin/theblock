"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, fetchApi } from "@/lib/api";

interface Owner {
  display_name: string;
  email: string;
}

export function useOwner() {
  const router = useRouter();
  const [owner, setOwner] = useState<Owner | null>(null);

  useEffect(() => {
    let active = true;
    fetchApi<{ owner: Owner }>("/api/owner/current")
      .then((response) => {
        if (active) setOwner(response.owner);
      })
      .catch((error) => {
        if (active && error instanceof ApiError && error.status === 401) router.replace("/login");
      });
    return () => {
      active = false;
    };
  }, [router]);

  return owner;
}
