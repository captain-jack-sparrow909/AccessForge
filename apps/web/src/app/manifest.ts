import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'AccessForge',
    short_name: 'AccessForge',
    description: 'Transparent co-design for low-risk assistive adapter candidates.',
    start_url: '/',
    display: 'standalone',
    background_color: '#f5f7f3',
    theme_color: '#236b4d',
  };
}
