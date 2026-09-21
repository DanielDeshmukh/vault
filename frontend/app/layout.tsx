import type { Metadata, Viewport } from "next";
import { Space_Grotesk, Space_Mono } from "next/font/google";
import "./globals.css";

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["400", "500", "600", "700"],
});

const spaceMono = Space_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "700"],
});

const SITE_URL = "https://vault-rbac-rag.vercel.app";

export const metadata: Metadata = {
  title: {
    default: "Vault - Enterprise Knowledge System",
    template: "%s | Vault",
  },
  description:
    "Permission-aware enterprise knowledge retrieval with RBAC, hybrid search, AI-powered answers, and document management. Built for teams that need secure, role-based access to organizational knowledge.",
  keywords: [
    "enterprise knowledge management",
    "RBAC",
    "role-based access control",
    "document retrieval",
    "AI search",
    "knowledge base",
    "enterprise search",
    "permission-aware",
    "Cohere AI",
    "vector search",
  ],
  authors: [{ name: "Daniel Deshmukh" }],
  creator: "Daniel Deshmukh",
  publisher: "Vault",
  metadataBase: new URL(SITE_URL),
  openGraph: {
    type: "website",
    locale: "en_US",
    url: SITE_URL,
    siteName: "Vault",
    title: "Vault - Enterprise Knowledge System",
    description:
      "Permission-aware enterprise knowledge retrieval with RBAC, hybrid search, AI-powered answers, and document management.",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "Vault - Enterprise Knowledge System",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Vault - Enterprise Knowledge System",
    description:
      "Permission-aware enterprise knowledge retrieval with RBAC, hybrid search, and AI-powered answers.",
    images: ["/og-image.png"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  manifest: "/manifest.json",
  icons: {
    icon: "/tab-icon.png",
    apple: "/tab-icon.png",
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Vault",
  },
  formatDetection: {
    telephone: false,
  },
};

export const viewport: Viewport = {
  themeColor: "#010102",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <head>
        <meta name="mobile-web-app-capable" content="yes" />
      </head>
      <body className={`${spaceGrotesk.variable} ${spaceMono.variable} font-body antialiased`}>{children}</body>
    </html>
  );
}
