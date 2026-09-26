import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "www.google.com", pathname: "/s2/favicons" },
      { protocol: "https", hostname: "**" }, // og:image artikel (dimuat tanpa optimasi)
    ],
  },
};

export default nextConfig;
