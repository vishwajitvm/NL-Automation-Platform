import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NL-Automation Platform",
  description: "Natural Language Automation Platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
