import type { NextConfig } from "next";
const config: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXTROLE_API || "http://127.0.0.1:8090"}/api/:path*`,
      },
    ];
  },
};
export default config;
