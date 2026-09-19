import type { Metadata, Viewport } from "next";
import { Inter, Space_Grotesk, Space_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-display",
});

const spaceMono = Space_Mono({
  weight: ["400", "700"],
  subsets: ["latin"],
  variable: "--font-mono",
});

const SITE_URL = "https://vault-rbac-rag.vercel.app";

export const metadata: Metadata = {
  title: {
    default: "Vault - Permission-Aware Enterprise Knowledge",
    template: "%s | Vault",
  },
  description:
    "RBAC-enforced RAG system. Pre-retrieval permission filtering ensures unauthorized content never reaches the language model.",
  keywords: [
    "RBAC",
    "RAG",
    "permission-aware retrieval",
    "enterprise knowledge",
    "role-based access control",
    "vector search",
    "Pinecone",
    "Cohere",
    "FastAPI",
    "Next.js",
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
    title: "Vault - Permission-Aware Enterprise Knowledge",
    description:
      "RBAC-enforced RAG system. Pre-retrieval permission filtering ensures unauthorized content never reaches the language model.",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "Vault - Permission-Aware Enterprise Knowledge",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Vault - Permission-Aware Enterprise Knowledge",
    description:
      "RBAC-enforced RAG system. Pre-retrieval permission filtering ensures unauthorized content never reaches the language model.",
    images: ["/og-image.png"],
  },
  robots: {
    index: true,
    follow: true,
  },
  manifest: "/manifest.json",
  icons: {
    icon: "/tab-icon.png",
    apple: "/tab-icon.png",
  },
};

export const viewport: Viewport = {
  themeColor: "#000000",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
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
      <body className={`${inter.variable} ${spaceGrotesk.variable} ${spaceMono.variable} font-body antialiased`}>
        {children}
      </body>
    </html>
  );
}
