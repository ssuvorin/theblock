const namedAvatars: Record<string, string> = {
  alex: "/avatars/alex.png",
  "alex ivanov": "/avatars/alex.png",
  daniel: "/avatars/daniel.png",
  "daniel ruiz": "/avatars/daniel.png",
  john: "/avatars/tom.png",
  lena: "/avatars/lena.png",
  "lena groß": "/avatars/lena.png",
  marta: "/avatars/marta.png",
  nadia: "/avatars/nadia.png",
  "nadia haddad": "/avatars/nadia.png",
  omar: "/avatars/omar.png",
  "omar farouk": "/avatars/omar.png",
  ruth: "/avatars/ruth.png",
  sergey: "/avatars/sergey.png",
  "sergey lapin": "/avatars/sergey.png",
  tom: "/avatars/tom.png",
  "tom becker": "/avatars/tom.png",
};

export function avatarFor(name: string, photoUrl?: string | null): string | null {
  if (photoUrl) return photoUrl;
  return namedAvatars[name.trim().toLowerCase()] ?? null;
}

export function initialsFor(name: string): string {
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "?";
}
