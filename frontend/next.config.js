/** @type {import('next').NextConfig} */
module.exports = {
  async rewrites() {
    return [
      // This single, comprehensive rule will proxy all API requests.
      // It's more robust and avoids potential issues with multiple, overlapping rules.
      {
        source: '/api/:path*',
        destination: `${process.env.BACKEND_URL || 'http://127.0.0.1:5000'}/:path*`,
      },
    ]
  },
  typescript: { ignoreBuildErrors: true },
};
