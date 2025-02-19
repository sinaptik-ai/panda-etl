const nextConfig = {
  swcMinify: false, // TODO - track and remove this later: https://github.com/wojtekmaj/react-pdf/issues/1822
  async rewrites() {
    const backendUrl =
      process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;

    if (!backendUrl) {
      console.warn(
        "Warning: No backend URL provided. API routes may not work correctly."
      );
    }

    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/v1/:path*`,
      },
      {
        source: "/assets/:path*",
        destination: `${backendUrl}/assets/:path*`,
      },
    ];
  },
};

export default nextConfig;
