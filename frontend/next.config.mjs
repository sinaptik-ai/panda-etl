const nextConfig = {
  swcMinify: false, // TODO - track and remove this later: https://github.com/wojtekmaj/react-pdf/issues/1822
  async rewrites() {
    return [
      // {
      //   source: "/api/:path*",
      //   destination: "http://localhost:5328/:path*",
      // },
      {
        source: "/assets/:path*",
        destination: "http://localhost:5328/assets/:path*",
      },
    ];
  },
};

export default nextConfig;
