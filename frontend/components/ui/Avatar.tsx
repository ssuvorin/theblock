import Image from "next/image";
import { avatarFor, initialsFor } from "@/lib/avatar";
import { cx } from "@/lib/cx";

interface AvatarProps {
  name: string;
  src?: string | null;
  size?: number;
  path?: boolean;
  you?: boolean;
  className?: string;
}

export function Avatar({ name, src, size = 40, path, you, className }: AvatarProps) {
  const imageSource = avatarFor(name, src);
  const classes = cx("avatar", path && "avatar-path", you && "avatar-you", className);

  if (!imageSource) {
    return <span className={cx(classes, "avatar-fallback")} style={{ width: size, height: size }}>{initialsFor(name)}</span>;
  }

  return (
    <Image
      unoptimized
      src={imageSource}
      alt={`${name} avatar`}
      width={size}
      height={size}
      className={classes}
      style={{ width: size, height: size }}
    />
  );
}
