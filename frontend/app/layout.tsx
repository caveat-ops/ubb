import './globals.css';
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' });

export const metadata: Metadata = {
  metadataBase: new URL('https://universidade-bebe.com'),
  title: 'Universidade Bebê — Cybersecurity Knowledge Graph',
  description: 'Curadoria viva de cybersegurança organizada por disciplinas, trilhas e conhecimento conectado.',
  openGraph: {
    title: 'Universidade Bebê',
    description: 'Vem cá bebê, deixa eu te ensinar.',
    images: [],
  },
  twitter: {
    card: 'summary_large_image',
    images: [],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className="dark">
      <body className={`${inter.variable} font-sans bg-[#070707] text-[#f5f5f5] min-h-screen`}>
        {children}
      </body>
    </html>
  );
}
