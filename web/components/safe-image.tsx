"use client";

import Image, { type ImageProps } from "next/image";
import { useState } from "react";

/** next/image yang menghilang bila gagal dimuat, sehingga latar cadangan di bawahnya terlihat. */
export function SafeImage({ alt, ...props }: ImageProps) {
  const [failed, setFailed] = useState(false);
  if (failed) return null;
  return <Image alt={alt} {...props} onError={() => setFailed(true)} />;
}
