/** @type {import('next').NextConfig} */
const nextConfig = {
  eslint: {
    ignoreDuringBuilds: true,
  },
  images: { unoptimized: true },
  async headers() {
    const isDev = process.env.NODE_ENV !== 'production';
    const corsOrigin = isDev ? '*' : (process.env.CORS_ORIGIN || '*');
    const domain = process.env.DOMAIN || 'localhost';

    return [
      {
        source: '/(.*)',
        headers: [
          { key: 'Content-Security-Policy', value: "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self' https: http://localhost:* ws://localhost:*; frame-ancestors 'none'; base-uri 'self'; form-action 'self'" },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
          { key: 'Strict-Transport-Security', value: 'max-age=63072000; includeSubDomains; preload' },
          { key: 'Access-Control-Allow-Origin', value: corsOrigin },
          { key: 'Access-Control-Allow-Methods', value: 'GET, POST, PUT, DELETE, OPTIONS' },
          { key: 'Access-Control-Allow-Headers', value: 'Content-Type, Authorization' },
        ],
      },
    ];
  },
  async rewrites() {
    const apiUrl = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://api:8000';
    const syncUrl = process.env.SYNC_URL;
    const rules = [];

    if (syncUrl) {
      rules.push({
        source: '/api/sync/:path*',
        destination: `${syncUrl}/api/sync/:path*`,
      });
    }

    rules.push({
      source: '/api/:path*',
      destination: `${apiUrl}/api/:path*`,
    });

    return rules;
  },
};

module.exports = nextConfig;
